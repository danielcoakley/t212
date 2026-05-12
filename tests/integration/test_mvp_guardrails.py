"""Offline integration guardrails for the MVP operator workflow."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from isa_system.api.deps import STATE
from isa_system.api.main import app
from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.domain.enums import RuntimeMode
from isa_system.services.deep_research import (
    DeepResearchDecision,
    DeepResearchInput,
    DeepResearchReview,
    DeepResearchStatus,
)
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendations import (
    RecommendationsResponse,
    build_recommendations_from_static_data,
)
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics
from isa_system.settings import Settings
from isa_system.utils.time import now_utc


@pytest.fixture(autouse=True)
def reset_control_state() -> Iterator[None]:
    """Keep process-local mode mutations from leaking between route tests."""

    STATE.mode = RuntimeMode.PREVIEW
    STATE.live_armed = False
    STATE.kill_switch_enabled = False
    yield
    STATE.mode = RuntimeMode.PREVIEW
    STATE.live_armed = False
    STATE.kill_switch_enabled = False


def test_health_route_reports_preview_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health remains local and preview-first when providers are unconfigured."""

    monkeypatch.setattr(
        "isa_system.api.routers.health.get_settings",
        lambda: Settings(_env_file=None),
    )

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "preview"
    assert payload["live_armed"] is False
    assert payload["kill_switch_enabled"] is False
    assert payload["subsystems"]["broker"] == "not_configured_ok"


def test_recommendation_handoff_requires_research_before_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broker-matched buy still cannot hand off without a current research pass."""

    recommendations = _recommendations_response(["GOOD.L"])
    validation = validate_recommendation_instruments(
        recommendations,
        instruments=[_instrument("GOOD.L")],
    )
    monkeypatch.setattr(
        "isa_system.api.routers.recommendations._recommendations_for_validation",
        lambda candidates, include_defaults: recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.recommendations.validate_recommendation_instruments",
        lambda response: validation,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.recommendations.latest_deep_research_reviews",
        lambda symbols: {},
    )

    response = TestClient(app).get(
        "/recommendations/handoff",
        params=[("candidates", "GOOD.L"), ("include_defaults", "false")],
    )

    assert response.status_code == 200
    payload = response.json()
    row = payload["rows"][0]
    assert row["proposed_preview_action"] == "BUY"
    assert row["handoff_status"] == "REVIEW_REQUIRED"
    assert row["eligible_for_preview"] is False
    assert row["instrument_validation_status"] == "BROKER_MATCHED"
    assert row["research_review_status"] == "MISSING"
    assert "DEEP_RESEARCH_REQUIRED" in row["blockers"]
    assert any("never submits orders" in warning for warning in payload["warnings"])


def test_recommendation_preview_sizes_only_rows_with_research_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selected rows return preview-only sizing while unapproved buys stay notional-zero."""

    recommendations = _recommendations_response(["GOOD.L", "WAIT.L"])
    validation = validate_recommendation_instruments(
        recommendations,
        instruments=[_instrument("GOOD.L"), _instrument("WAIT.L")],
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio",
        lambda: _snapshot(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_broker_market_scan_universe",
        lambda: SimpleNamespace(symbols=["GOOD.L", "WAIT.L"]),
    )

    def fake_recommendations(
        snapshot: object,
        candidates: list[str],
        include_default_candidates: bool,
        default_candidates: list[str],
        include_llm_rationale: bool,
    ) -> RecommendationsResponse:
        return recommendations

    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendations",
        fake_recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.validate_recommendation_instruments",
        lambda response: validation,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.latest_deep_research_reviews",
        lambda symbols: {"GOOD.L": _research_review("GOOD.L")},
    )

    response = TestClient(app).post(
        "/rebalances/from-recommendations/preview",
        json={"symbols": ["GOOD.L", "WAIT.L"], "total_equity_gbp": 10000},
    )

    assert response.status_code == 200
    payload = response.json()
    rows = {row["research_symbol"]: row for row in payload["rows"]}
    assert payload["mode"] == "preview"
    assert payload["selected_count"] == 2
    assert payload["eligible_count"] == 1
    assert any("does not submit orders" in warning for warning in payload["warnings"])
    assert rows["GOOD.L"]["eligible"] is True
    assert rows["GOOD.L"]["side"] == "BUY"
    assert rows["GOOD.L"]["estimated_notional_gbp"] == 400.0
    assert rows["GOOD.L"]["research_review_status"] == "RESEARCH_PASSED"
    assert "order_id" not in rows["GOOD.L"]
    assert rows["WAIT.L"]["eligible"] is False
    assert rows["WAIT.L"]["estimated_notional_gbp"] == 0.0
    assert "DEEP_RESEARCH_REQUIRED" in rows["WAIT.L"]["blockers"]


def test_live_submit_route_does_not_exist() -> None:
    """The unified build exposes no live submit endpoint."""

    client = TestClient(app)
    mode_response = client.post("/modes/live")
    submit_response = client.post(
        "/rebalances/submit",
        json={"batch_hash": "review-table-preview", "mode": "live"},
    )

    assert mode_response.status_code == 200
    assert mode_response.json()["mode"] == "live"
    assert mode_response.json()["live_armed"] == "False"
    assert submit_response.status_code == 404


def _snapshot() -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, 9, 0, tzinfo=UTC),
        account_currency="GBP",
        total_value=10_000,
        available_to_trade=10_000,
        positions=[],
        warnings=[],
    )


def _recommendations_response(symbols: list[str]) -> RecommendationsResponse:
    data = {
        symbol: HoldingValuationData(
            symbol=symbol,
            retrieved_at_utc=datetime(2026, 5, 11, 9, 1, tzinfo=UTC),
            daily_adjusted_closes=_rising_closes(260),
            valuation=ValuationMetrics(
                trailing_pe=8.0,
                forward_pe=7.0,
                price_to_book=1.0,
                dividend_yield=0.05,
            ),
        )
        for symbol in symbols
    }
    return build_recommendations_from_static_data(
        _snapshot(),
        data,
        candidates=symbols,
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 11, 9, 2, tzinfo=UTC),
    )


def _rising_closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]


def _instrument(symbol: str) -> Trading212Instrument:
    root = symbol.removesuffix(".L")
    return Trading212Instrument(ticker=f"{root}l_EQ", currencyCode="GBX", type="STOCK")


def _research_review(symbol: str) -> DeepResearchReview:
    generated = now_utc()
    return DeepResearchReview(
        id=f"review-{symbol}",
        symbol=symbol,
        research_symbol=symbol,
        broker_ticker=_instrument(symbol).ticker,
        status=DeepResearchStatus.AVAILABLE,
        decision=DeepResearchDecision.RESEARCH_PASSED,
        thesis="Evidence supports review-only preview sizing.",
        final_score=82,
        model="test-model",
        evidence_hash="hash",
        generated_at_utc=generated,
        expires_at_utc=generated + timedelta(days=7),
        request=DeepResearchInput(
            symbol=symbol,
            research_symbol=symbol,
            broker_ticker=_instrument(symbol).ticker,
            action="REVIEW_BUY",
            source="watchlist",
            component_scores={"composite": 0.5},
            valuation={},
            technicals={},
        ),
    )
