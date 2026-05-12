"""Broad-market recommendation screener backed by Trading 212 metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.market_scan import (
    DEFAULT_BROKER_SCAN_LIMIT,
    DEFAULT_DISPLAY_LIMIT,
    load_odp_market_scan_universe,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, load_trading212_portfolio
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendations import RecommendationAction, build_recommendations
from isa_system.settings import Settings
from isa_system.utils.time import require_utc


class ScreenerRow(BaseModel):
    """One broad-market screener row."""

    symbol: str
    research_symbol: str
    source: str
    action: RecommendationAction
    composite_score: float
    fundamental_score: float | None = None
    technical_score: float | None = None
    catalyst_score: float | None = None
    sentiment_score: float | None = None
    broker_validation_status: str | None = None
    broker_ticker: str | None = None
    currency: str | None = None
    asset_type: str | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    eligible_for_preview: bool = False
    research_review_status: str | None = None


class MarketScreenerResponse(BaseModel):
    """Current broad-market screener output."""

    status: str
    environment: str
    generated_at_utc: datetime
    source: str
    total_candidates: int
    displayed_count: int
    filters_applied: dict[str, Any]
    rows: list[ScreenerRow]
    warnings: list[str] = Field(default_factory=list)


def build_market_screener(
    *,
    snapshot: BrokerPortfolioSnapshot | None = None,
    settings: Settings | None = None,
    max_loaded: int = DEFAULT_BROKER_SCAN_LIMIT,
    top_n: int = DEFAULT_DISPLAY_LIMIT,
) -> MarketScreenerResponse:
    """Run a broad broker-universe scan and return review-only rows."""

    broker_snapshot = snapshot or load_trading212_portfolio(settings)
    universe = load_odp_market_scan_universe(settings=settings, max_symbols=top_n)
    recommendations = build_recommendations(
        broker_snapshot,
        candidates=[],
        include_default_candidates=True,
        default_candidates=universe.symbols,
        include_llm_rationale=False,
    )
    validation = validate_recommendation_instruments(recommendations, settings=settings)
    handoff = build_recommendation_handoff(recommendations, instrument_validation=validation)
    validation_by_symbol = {row.research_symbol.upper(): row for row in validation.rows}
    handoff_by_symbol = {row.research_symbol.upper(): row for row in handoff.rows}
    rows = []
    for item in recommendations.recommendations:
        candidate = item.candidate
        key = candidate.research_symbol.upper()
        validation_row = validation_by_symbol.get(key)
        handoff_row = handoff_by_symbol.get(key)
        rows.append(
            ScreenerRow(
                symbol=candidate.symbol,
                research_symbol=candidate.research_symbol,
                source=candidate.source,
                action=item.action,
                composite_score=item.scores.composite,
                fundamental_score=item.scores.fundamental_valuation.score,
                technical_score=item.scores.technical.score,
                catalyst_score=item.scores.catalysts.score,
                sentiment_score=item.scores.sentiment_news.score,
                broker_validation_status=(
                    validation_row.status.value if validation_row is not None else None
                ),
                broker_ticker=validation_row.broker_ticker if validation_row else None,
                currency=validation_row.currency if validation_row else candidate.currency,
                asset_type=validation_row.asset_type if validation_row else None,
                blockers=handoff_row.blockers if handoff_row else list(item.risk_flags),
                warnings=list(item.warnings),
                eligible_for_preview=handoff_row.eligible_for_preview if handoff_row else False,
                research_review_status=(
                    handoff_row.research_review_status if handoff_row else None
                ),
            )
        )
    rows.sort(
        key=lambda row: (_screener_rank(row.action), -row.composite_score, row.research_symbol)
    )
    displayed = rows[:top_n]
    return MarketScreenerResponse(
        status=broker_snapshot.status,
        environment=broker_snapshot.environment,
        generated_at_utc=require_utc(recommendations.retrieved_at_utc),
        source=universe.source_path or universe.name,
        total_candidates=len(rows),
        displayed_count=len(displayed),
        filters_applied={
            "broker_loaded_cap": max_loaded,
            "display_cap": top_n,
            "universe_name": universe.name,
        },
        rows=displayed,
        warnings=[*universe.warnings, *recommendations.warnings, *validation.warnings],
    )


def _screener_rank(action: RecommendationAction) -> int:
    return {
        RecommendationAction.REVIEW_BUY: 0,
        RecommendationAction.WATCH: 1,
        RecommendationAction.HOLD: 2,
        RecommendationAction.REVIEW_SELL: 3,
        RecommendationAction.BLOCKED: 4,
    }[action]
