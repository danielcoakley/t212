"""Tests for dashboard factor attribution helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from isa_system.dashboard.factor_context import (
    factor_attribution_frame,
    factor_coverage_summary,
)
from isa_system.services.valuation import (
    HoldingsValuationResponse,
    HoldingValuation,
    TechnicalIndicators,
    ValuationMetrics,
)


def test_factor_attribution_frame_ranks_available_scores() -> None:
    """Current holdings receive deterministic starter composite ranks."""

    frame = factor_attribution_frame(
        _response(
            [
                _holding("AAPL_US_EQ", "AAPL", momentum=0.20, trailing_pe=20, dividend=0.01),
                _holding("MSFT_US_EQ", "MSFT", momentum=0.05, trailing_pe=40, dividend=0.005),
            ]
        )
    )

    assert list(frame["rank"]) == [1, 2]
    assert frame.iloc[0]["symbol"] == "AAPL_US_EQ"
    assert frame.iloc[0]["composite_score"] > frame.iloc[1]["composite_score"]


def test_factor_coverage_summary_counts_missing_quality() -> None:
    """Coverage keeps quality explicit as pending official-fundamental work."""

    frame = factor_attribution_frame(
        _response([_holding("SHEL_GB_EQ", "SHEL.L", momentum=None, trailing_pe=None)])
    )
    coverage = factor_coverage_summary(frame)

    assert coverage == {"holdings": 1, "momentum": 0, "value": 0, "dividend": 0, "quality": 0}
    assert "quality" in frame.iloc[0]["missing_factors"]


def _response(holdings: list[HoldingValuation]) -> HoldingsValuationResponse:
    return HoldingsValuationResponse(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
        provider="static",
        holdings=holdings,
        warnings=[],
    )


def _holding(
    symbol: str,
    research_symbol: str,
    *,
    momentum: float | None,
    trailing_pe: float | None,
    dividend: float | None = None,
) -> HoldingValuation:
    return HoldingValuation(
        symbol=symbol,
        broker_ticker=symbol,
        research_symbol=research_symbol,
        name=research_symbol,
        currency="USD",
        quantity=1,
        current_value=100,
        valuation=ValuationMetrics(trailing_pe=trailing_pe, dividend_yield=dividend),
        technicals=TechnicalIndicators(momentum_3m=momentum),
        upcoming_events=[],
        news=[],
        sentiment=None,
        warnings=[],
    )
