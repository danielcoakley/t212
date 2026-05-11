"""Tests for the side-effect-free operator report shell."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from isa_system.db.session import init_db, make_engine, make_session_factory
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
from isa_system.services.operator_report import (
    OperatorManagementStatus,
    build_management_report_status,
    build_operator_report,
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


def test_operator_report_marks_missing_sections_explicitly() -> None:
    """A report shell with no inputs does not imply completeness."""

    report = build_operator_report(as_of_utc=_now())
    sections = {section.key: section for section in report.sections}

    assert report.status == "partial"
    assert set(sections) == {
        "account",
        "recommendations",
        "research",
        "preview",
        "pilot_paper",
        "management",
    }
    assert sections["account"].status == "missing"
    assert sections["preview"].missing_data == ["recommendation_preview"]
    assert sections["pilot_paper"].missing_data == ["pilot_paper_workflow"]
    assert "## Preview" in report.markdown
    assert any("Preview has missing data" in warning for warning in report.warnings)


def test_operator_report_aggregates_available_mvp_evidence() -> None:
    """Available account/recommendation/research/preview/paper inputs produce report sections."""

    generated_at = _now()
    snapshot = BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=generated_at,
        account_currency="GBP",
        total_value=10_000.0,
        available_to_trade=1_000.0,
        reserved_for_orders=0.0,
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
    validation = InstrumentValidationResponse(
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

    report = build_operator_report(
        account_snapshot=snapshot,
        recommendations=recommendations,
        handoff=handoff,
        research_reviews={"GOOD.L": review},
        preview=preview,
        pilot_workflow=workflow,
        management=OperatorManagementStatus(
            runtime_mode="preview",
            live_armed=False,
            kill_switch_enabled=False,
            broker_credentials_configured=True,
            deep_research_configured=True,
        ),
        as_of_utc=generated_at,
    )
    sections = {section.key: section for section in report.sections}

    assert report.status == "available"
    assert sections["account"].status == "available"
    assert sections["recommendations"].records[0]["eligible_for_preview"] is True
    assert sections["research"].items[1].value == 1
    assert sections["preview"].status == "available"
    assert sections["pilot_paper"].missing_data == ["paper_persistence", "paper_reconciliation"]
    assert sections["management"].status == "available"
    assert "GOOD.L" in report.markdown


def test_operator_report_includes_persisted_paper_cycle_evidence() -> None:
    """A supplied persisted paper cycle replaces the simulated-only persistence gap."""

    generated_at = _now()
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

    report = build_operator_report(
        pilot_workflow=workflow,
        persisted_paper_cycle=persisted,
        as_of_utc=generated_at,
    )
    section = {section.key: section for section in report.sections}["pilot_paper"]
    items = {item.label: item.value for item in section.items}

    assert section.status == "available"
    assert section.missing_data == ["paper_reconciliation"]
    assert "paper_persistence" not in section.missing_data
    assert items["Evidence source"] == "simulated_and_persisted_paper_cycle"
    assert items["Paper cycle ID"] == persisted.id
    assert items["Persistence status"] == "persisted"
    assert items["Reconciliation status"] == "not_available"
    assert items["Intent rows"] == 1
    assert items["Simulated fills"] == 1
    assert items["Total expected notional GBP"] == "400.00"
    assert section.records[0]["paper_cycle_id"] == persisted.id
    assert section.records[0]["simulated_fill_count"] == 1
    assert any("not reconciled" in warning for warning in section.warnings)
    assert persisted.id in report.markdown


def test_management_report_status_never_exposes_secret_values() -> None:
    """Management report status collapses credentials into booleans only."""

    status = build_management_report_status(
        Settings(
            _env_file=None,
            trading212_api_key=SecretStr("broker-key"),
            trading212_api_secret=SecretStr("broker-secret"),
            openai_api_key=SecretStr("openai-key"),
        )
    )

    assert status.broker_credentials_configured is True
    assert status.deep_research_configured is True
    assert "broker-key" not in status.model_dump_json()
    assert "openai-key" not in status.model_dump_json()


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


def _now() -> datetime:
    return datetime(2026, 5, 11, 12, tzinfo=UTC)
