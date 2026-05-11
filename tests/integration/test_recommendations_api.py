"""Tests for recommendation API routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.recommendations import build_recommendations_from_static_data
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics


def test_recommendations_endpoint_is_offline_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint can be exercised without broker or market-data network access."""

    def fake_snapshot() -> BrokerPortfolioSnapshot:
        return BrokerPortfolioSnapshot(
            status="not_configured",
            environment="demo",
            retrieved_at_utc=datetime(2026, 5, 10, 10, 0, tzinfo=UTC),
            positions=[
                BrokerPosition(
                    symbol="AAPL_US_EQ",
                    broker_ticker="AAPL_US_EQ",
                    name="Apple",
                    currency="USD",
                    quantity=2,
                    current_value=400,
                )
            ],
            warnings=["Trading 212 credentials are not configured."],
        )

    static_data = {
        "AAPL": HoldingValuationData(
            symbol="AAPL",
            retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
            daily_adjusted_closes=_closes(260),
            valuation=ValuationMetrics(
                trailing_pe=18.0,
                forward_pe=16.0,
                price_to_book=3.0,
                dividend_yield=0.01,
            ),
        ),
        "TSCO.L": HoldingValuationData(
            symbol="TSCO.L",
            retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
            daily_adjusted_closes=_closes(260),
            valuation=ValuationMetrics(trailing_pe=11.0, dividend_yield=0.04),
        ),
    }

    monkeypatch.setattr(
        "isa_system.api.routers.recommendations.load_trading212_portfolio",
        fake_snapshot,
    )

    def fake_recommendations(
        snapshot: BrokerPortfolioSnapshot,
        candidates: list[str] | None,
        include_default_candidates: bool,
        default_candidates: list[str],
        include_llm_rationale: bool,
    ) -> object:
        return build_recommendations_from_static_data(
            snapshot,
            static_data,
            candidates=candidates,
            include_default_candidates=include_default_candidates,
            default_candidates=default_candidates,
            include_llm_rationale=include_llm_rationale,
            as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
        )

    monkeypatch.setattr(
        "isa_system.api.routers.recommendations.build_recommendations",
        fake_recommendations,
    )

    response = TestClient(app).get(
        "/recommendations",
        params=[("candidates", "TSCO.L"), ("include_defaults", "false")],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "static"
    assert "Trading 212 credentials are not configured." in payload["warnings"]
    symbols = {item["candidate"]["research_symbol"] for item in payload["recommendations"]}
    assert symbols == {"AAPL", "TSCO.L"}
    assert {item["action"] for item in payload["recommendations"]} <= {
        "HOLD",
        "WATCH",
        "REVIEW_BUY",
        "REVIEW_SELL",
        "BLOCKED",
    }

    scan_response = TestClient(app).get("/recommendations/scan-universe")

    assert scan_response.status_code == 200
    scan_payload = scan_response.json()
    assert "symbols" in scan_payload
    assert scan_payload["symbols"]

    handoff_response = TestClient(app).get(
        "/recommendations/handoff",
        params=[("candidates", "TSCO.L"), ("include_defaults", "false")],
    )

    assert handoff_response.status_code == 200
    handoff = handoff_response.json()
    assert handoff["provider"] == "static"
    assert handoff["eligible_count"] >= 0
    assert handoff["review_required_count"] >= 0
    assert {row["handoff_status"] for row in handoff["rows"]} <= {
        "ELIGIBLE",
        "REVIEW_REQUIRED",
        "BLOCKED",
        "NO_ACTION",
    }

    instrument_response = TestClient(app).get(
        "/recommendations/instrument-validation",
        params=[("candidates", "TSCO.L"), ("include_defaults", "false")],
    )

    assert instrument_response.status_code == 200
    instruments = instrument_response.json()
    assert instruments["provider"] == "trading212"
    assert {row["status"] for row in instruments["rows"]} <= {
        "HOLDING_CONFIRMED",
        "BROKER_MATCHED",
        "NEEDS_MAPPING",
        "NOT_CONFIGURED",
        "ERROR",
    }


def _closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]
