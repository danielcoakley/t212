"""Integration tests for MVP screener, research, and preview routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.deep_research import (
    DeepResearchDecision,
    DeepResearchInput,
    DeepResearchReview,
    DeepResearchStatus,
)
from isa_system.services.market_screener import MarketScreenerResponse, ScreenerRow
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    RecommendationPreviewRow,
)
from isa_system.services.recommendations import (
    RecommendationAction,
    build_recommendations_from_static_data,
)
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics
from isa_system.settings import Settings


def test_screener_endpoint_returns_broad_market_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """The screener endpoint exposes consolidated broad-market candidates."""

    monkeypatch.setattr(
        "isa_system.api.routers.recommendations.build_market_screener",
        lambda max_loaded, top_n: MarketScreenerResponse(
            status="live",
            environment="live",
            generated_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            source="trading212:/equity/metadata/instruments",
            total_candidates=1,
            displayed_count=1,
            filters_applied={"broker_loaded_cap": max_loaded, "display_cap": top_n},
            rows=[
                ScreenerRow(
                    symbol="GOOD.L",
                    research_symbol="GOOD.L",
                    source="watchlist",
                    action=RecommendationAction.REVIEW_BUY,
                    composite_score=0.55,
                    broker_validation_status="BROKER_MATCHED",
                    broker_ticker="GOODl_EQ",
                    eligible_for_preview=False,
                    research_review_status="MISSING",
                    blockers=["DEEP_RESEARCH_REQUIRED"],
                )
            ],
        ),
    )

    response = TestClient(app).get("/recommendations/screener")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "trading212:/equity/metadata/instruments"
    assert payload["rows"][0]["research_review_status"] == "MISSING"


def test_research_review_latest_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Latest research endpoint returns persisted review shape."""

    review = _review("GOOD.L")
    monkeypatch.setattr(
        "isa_system.api.routers.research_reviews.latest_deep_research_review",
        lambda symbol: review,
    )

    response = TestClient(app).get("/research-reviews/latest", params={"symbol": "GOOD.L"})

    assert response.status_code == 200
    assert response.json()["decision"] == "RESEARCH_PASSED"


def test_research_review_run_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Research run endpoint finds a candidate and returns the LLM gate result."""

    review = _review("GOOD.L")
    response_model = build_recommendations_from_static_data(
        BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            positions=[],
            warnings=[],
        ),
        {
            "GOOD.L": HoldingValuationData(
                symbol="GOOD.L",
                retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
                daily_adjusted_closes=[
                    DailyAdjustedClose(
                        ts_utc=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index),
                        adj_close=float(index + 1),
                    )
                    for index in range(260)
                ],
                valuation=ValuationMetrics(trailing_pe=8.0, dividend_yield=0.05),
            )
        },
        candidates=["GOOD.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.research_reviews._recommendations",
        lambda: response_model,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.research_reviews.validate_recommendation_instruments",
        lambda recommendations: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.research_reviews.build_recommendation_handoff",
        lambda recommendations, instrument_validation: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.research_reviews.run_deep_research",
        lambda request: review,
    )

    response = TestClient(app).post("/research-reviews/run", json={"symbol": "GOOD.L"})

    assert response.status_code == 200
    assert response.json()["status"] == "AVAILABLE"


def test_recommendation_preview_endpoint_is_preview_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recommendation preview route returns sizing rows without submitting orders."""

    def fake_recommendations(
        snapshot: object,
        candidates: list[str],
        include_default_candidates: bool,
        default_candidates: list[str],
        include_llm_rationale: bool,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            recommendations=[SimpleNamespace(candidate=SimpleNamespace(research_symbol="GOOD.L"))]
        )

    def fake_preview(
        selected_symbols: list[str],
        snapshot: object,
        handoff: object,
        total_equity_gbp: object,
    ) -> RecommendationPreviewResponse:
        return RecommendationPreviewResponse(
            generated_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            total_equity_gbp=10000.0,
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

    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio",
        lambda: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_broker_market_scan_universe",
        lambda: type("Universe", (), {"symbols": ["GOOD.L"]})(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendations",
        fake_recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.validate_recommendation_instruments",
        lambda recommendations: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.latest_deep_research_reviews",
        lambda symbols: {},
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendation_handoff",
        lambda recommendations, instrument_validation, research_reviews: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_preview_from_recommendation_handoff",
        fake_preview,
    )

    response = TestClient(app).post(
        "/rebalances/from-recommendations/preview",
        json={"symbols": ["GOOD.L"], "total_equity_gbp": 10000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "preview"
    assert payload["rows"][0]["eligible"] is True


def test_pilot_workflow_endpoint_links_preview_to_paper_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pilot workflow route is side-effect free and returns paper comparison shell."""

    def fake_recommendations(
        snapshot: object,
        candidates: list[str],
        include_default_candidates: bool,
        default_candidates: list[str],
        include_llm_rationale: bool,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            recommendations=[SimpleNamespace(candidate=SimpleNamespace(research_symbol="GOOD.L"))]
        )

    def fake_preview(
        selected_symbols: list[str],
        snapshot: object,
        handoff: object,
        total_equity_gbp: object,
    ) -> RecommendationPreviewResponse:
        return RecommendationPreviewResponse(
            generated_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            total_equity_gbp=10000.0,
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

    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio",
        lambda: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_broker_market_scan_universe",
        lambda: type("Universe", (), {"symbols": ["GOOD.L"]})(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendations",
        fake_recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.validate_recommendation_instruments",
        lambda recommendations: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.latest_deep_research_reviews",
        lambda symbols: {},
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendation_handoff",
        lambda recommendations, instrument_validation, research_reviews: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_preview_from_recommendation_handoff",
        fake_preview,
    )

    response = TestClient(app).post(
        "/rebalances/from-recommendations/pilot-workflow",
        json={"symbols": ["GOOD.L"], "total_equity_gbp": 10000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "preview"
    assert payload["workflow_status"] == "ready_for_operator_review"
    assert payload["expected_vs_simulated_status"] == "all_expected_rows_simulated"
    assert payload["persistence_status"] == "not_persisted"
    assert payload["reconciliation_status"] == "not_available"
    assert payload["paper_simulation"]["source_kind"] == "recommendation_preview"
    assert payload["rows"][0]["expected_vs_simulated_status"] == "matched"
    assert any("Live broker submission" in warning for warning in payload["warnings"])


def test_paper_cycle_endpoint_persists_and_reloads_preview_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Paper cycle route explicitly persists preview intents and simulated fills."""

    settings = Settings(_env_file=None, operational_db_dsn=f"sqlite:///{tmp_path / 'ops.db'}")

    def fake_recommendations(
        snapshot: object,
        candidates: list[str],
        include_default_candidates: bool,
        default_candidates: list[str],
        include_llm_rationale: bool,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            recommendations=[SimpleNamespace(candidate=SimpleNamespace(research_symbol="GOOD.L"))]
        )

    def fake_preview(
        selected_symbols: list[str],
        snapshot: object,
        handoff: object,
        total_equity_gbp: object,
    ) -> RecommendationPreviewResponse:
        return RecommendationPreviewResponse(
            generated_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            total_equity_gbp=10000.0,
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

    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio",
        lambda: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_broker_market_scan_universe",
        lambda: type("Universe", (), {"symbols": ["GOOD.L"]})(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendations",
        fake_recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.validate_recommendation_instruments",
        lambda recommendations: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.latest_deep_research_reviews",
        lambda symbols: {},
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendation_handoff",
        lambda recommendations, instrument_validation, research_reviews: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_preview_from_recommendation_handoff",
        fake_preview,
    )
    monkeypatch.setattr("isa_system.services.paper_persistence.get_settings", lambda: settings)

    response = TestClient(app).post(
        "/rebalances/from-recommendations/paper-cycle",
        json={"symbols": ["GOOD.L"], "total_equity_gbp": 10000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persistence_status"] == "persisted"
    assert payload["reconciliation_status"] == "not_available"
    assert payload["intents"][0]["expected_vs_simulated_status"] == "matched"
    assert payload["simulated_fills"][0]["paper_intent_id"] == payload["intents"][0]["id"]
    assert payload["simulated_fills"][0]["notional_source_kind"].endswith("estimated_notional")

    reload_response = TestClient(app).get(f"/rebalances/paper-cycles/{payload['id']}")

    assert reload_response.status_code == 200
    assert reload_response.json()["id"] == payload["id"]


def _review(symbol: str) -> DeepResearchReview:
    generated = datetime(2026, 5, 10, tzinfo=UTC)
    return DeepResearchReview(
        id="review-test",
        symbol=symbol,
        research_symbol=symbol,
        broker_ticker="GOODl_EQ",
        status=DeepResearchStatus.AVAILABLE,
        decision=DeepResearchDecision.RESEARCH_PASSED,
        thesis="Research pass.",
        final_score=82,
        model="test-model",
        evidence_hash="hash",
        generated_at_utc=generated,
        expires_at_utc=generated + timedelta(days=7),
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
