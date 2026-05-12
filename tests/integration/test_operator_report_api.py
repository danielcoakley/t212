"""Integration coverage for the side-effect-free operator report route."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from isa_system.api.deps import STATE
from isa_system.api.main import app
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.domain.enums import RuntimeMode
from isa_system.services.deep_research import (
    DeepResearchDecision,
    DeepResearchInput,
    DeepResearchReview,
    DeepResearchStatus,
)
from isa_system.services.instrument_validation import (
    InstrumentValidationResponse,
    InstrumentValidationRow,
    InstrumentValidationStatus,
)
from isa_system.services.paper_persistence import PersistedPaperCycle, persist_pilot_paper_workflow
from isa_system.services.pilot_workflow import PilotPaperWorkflowSummary, build_pilot_paper_workflow
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    RecommendationPreviewRow,
)
from isa_system.services.recommendations import build_recommendations_from_static_data
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics
from isa_system.settings import Settings


def test_operator_report_route_returns_report_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The report route aggregates read-only context and does not submit orders."""

    generated_at = datetime(2026, 5, 11, 12, tzinfo=UTC)
    snapshot = BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=generated_at,
        account_currency="GBP",
        total_value=10_000.0,
        available_to_trade=1_000.0,
        positions=[],
        warnings=[],
    )
    recommendations = build_recommendations_from_static_data(
        snapshot,
        {
            "GOOD.L": HoldingValuationData(
                symbol="GOOD.L",
                retrieved_at_utc=generated_at,
                daily_adjusted_closes=[
                    DailyAdjustedClose(
                        ts_utc=generated_at - timedelta(days=260 - index),
                        adj_close=float(index + 1),
                    )
                    for index in range(260)
                ],
                valuation=ValuationMetrics(trailing_pe=8.0, dividend_yield=0.05),
            )
        },
        candidates=["GOOD.L"],
        include_default_candidates=False,
        as_of_utc=generated_at,
    )
    validation = _validation(generated_at)
    review = _review("GOOD.L", generated_at)
    handoff = build_recommendation_handoff(
        recommendations,
        instrument_validation=validation,
        research_reviews={"GOOD.L": review},
    )
    preview = RecommendationPreviewResponse(
        generated_at_utc=generated_at,
        total_equity_gbp=10_000.0,
        selected_count=1,
        eligible_count=1,
        estimated_total_cost_gbp=12.5,
        rows=[
            RecommendationPreviewRow(
                symbol="GOOD.L",
                research_symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                side="BUY",
                eligible=True,
                target_weight=0.04,
                estimated_notional_gbp=400.0,
                estimated_total_cost_gbp=12.5,
                research_review_status="RESEARCH_PASSED",
                rationale="Preview-only sizing.",
            )
        ],
    )
    workflow = build_pilot_paper_workflow(preview).model_copy(
        update={"generated_at_utc": generated_at}
    )
    persisted = _persisted_cycle(workflow)

    STATE.mode = RuntimeMode.PREVIEW
    STATE.live_armed = False
    STATE.kill_switch_enabled = False
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.get_settings",
        lambda: Settings(
            _env_file=None,
            trading212_api_key=SecretStr("key"),
            trading212_api_secret=SecretStr("secret"),
            openai_api_key=SecretStr("openai"),
        ),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.load_trading212_portfolio",
        lambda: snapshot,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.load_broker_market_scan_universe",
        lambda: type("Universe", (), {"symbols": ["GOOD.L"], "warnings": []})(),
    )

    def fake_recommendations(
        snapshot: object,
        candidates: list[str],
        include_default_candidates: bool,
        default_candidates: list[str],
        include_llm_rationale: bool,
    ) -> object:
        return recommendations

    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.build_recommendations",
        fake_recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.validate_recommendation_instruments",
        lambda recommendations: validation,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.latest_deep_research_reviews",
        lambda symbols: {"GOOD.L": review},
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.build_recommendation_handoff",
        lambda recommendations, instrument_validation, research_reviews: handoff,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.build_preview_from_recommendation_handoff",
        lambda selected_symbols, snapshot, handoff, total_equity_gbp: preview,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.build_pilot_paper_workflow",
        lambda preview: workflow,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.load_paper_cycle",
        lambda cycle_id: persisted if cycle_id == persisted.id else None,
    )

    response = TestClient(app).post(
        "/operator-report",
        json={"symbols": ["GOOD.L"], "total_equity_gbp": 10_000},
    )

    assert response.status_code == 200
    payload = response.json()
    sections = {section["key"]: section for section in payload["sections"]}
    assert payload["report_kind"] == "operator_report_shell"
    assert payload["status"] == "partial"
    assert sections["preview"]["records"][0]["eligible"] is True
    assert sections["pilot_paper"]["missing_data"] == [
        "paper_persistence",
        "paper_reconciliation",
    ]
    assert sections["management"]["status"] == "available"
    assert "Operator Report Shell" in payload["markdown"]
    assert any("never submits broker orders" in warning for warning in payload["warnings"])

    persisted_response = TestClient(app).post(
        "/operator-report",
        json={"paper_cycle_id": persisted.id},
    )

    assert persisted_response.status_code == 200
    persisted_payload = persisted_response.json()
    persisted_sections = {section["key"]: section for section in persisted_payload["sections"]}
    persisted_items = {
        item["label"]: item["value"] for item in persisted_sections["pilot_paper"]["items"]
    }
    assert persisted_sections["preview"]["status"] == "missing"
    assert persisted_sections["pilot_paper"]["missing_data"] == ["paper_reconciliation"]
    assert persisted_items["Paper cycle ID"] == persisted.id
    assert persisted_items["Persistence status"] == "persisted"
    assert persisted_items["Reconciliation status"] == "not_available"
    assert persisted_items["Intent rows"] == 1
    assert persisted_items["Total simulated notional GBP"] == "400.00"
    assert persisted_sections["pilot_paper"]["records"][0]["paper_cycle_id"] == persisted.id
    assert any(
        "not reconciled" in warning for warning in persisted_sections["pilot_paper"]["warnings"]
    )


def _validation(generated_at: datetime) -> InstrumentValidationResponse:
    return InstrumentValidationResponse(
        status="demo",
        environment="demo",
        retrieved_at_utc=generated_at,
        instrument_count=1,
        rows=[
            InstrumentValidationRow(
                symbol="GOOD.L",
                research_symbol="GOOD.L",
                source="watchlist",
                status=InstrumentValidationStatus.BROKER_MATCHED,
                broker_ticker="GOODl_EQ",
                name="Good Plc",
                isin="GB00GOOD0001",
                currency="GBP",
                asset_type="STOCK",
                candidate_broker_tickers=["GOODl_EQ"],
                isa_eligibility="requires_account_and_instrument_review",
                reason="Matched fixture.",
            )
        ],
    )


def _review(symbol: str, generated_at: datetime) -> DeepResearchReview:
    return DeepResearchReview(
        id="review-good",
        symbol=symbol,
        research_symbol=symbol,
        broker_ticker="GOODl_EQ",
        status=DeepResearchStatus.AVAILABLE,
        decision=DeepResearchDecision.RESEARCH_PASSED,
        thesis="Research pass.",
        final_score=82,
        model="test-model",
        evidence_hash="hash",
        generated_at_utc=generated_at,
        expires_at_utc=datetime(2099, 1, 1, tzinfo=UTC),
        request=DeepResearchInput(
            symbol=symbol,
            research_symbol=symbol,
            action="REVIEW_BUY",
            source="watchlist",
            component_scores={"composite": 0.5},
            valuation={},
            technicals={},
        ),
    )


def _persisted_cycle(workflow: PilotPaperWorkflowSummary) -> PersistedPaperCycle:
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        return persist_pilot_paper_workflow(workflow, session=session)
