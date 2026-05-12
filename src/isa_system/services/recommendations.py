"""Offline-safe recommendation service for holdings and market candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from isa_system.services.llm_rationale import (
    LLMRationaleRequest,
    LLMRationaleResponse,
    generate_llm_rationale,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import (
    HoldingValuation,
    HoldingValuationData,
    NewsItem,
    ODPScreenerValuationProvider,
    SentimentSnapshot,
    StaticValuationProvider,
    TechnicalIndicators,
    UpcomingEvent,
    ValuationMetrics,
    ValuationProvider,
    calculate_technicals,
    research_symbol_for_position,
)
from isa_system.utils.time import now_utc, require_utc

DEFAULT_MARKET_CANDIDATES = ["AAPL", "MSFT", "TSCO.L", "SHEL.L"]
EVENT_BLACKOUT_DAYS_BEFORE = 5
EVENT_BLACKOUT_DAYS_AFTER = 2


class RecommendationAction(StrEnum):
    """Human-review recommendation actions. Never submit live orders."""

    HOLD = "HOLD"
    WATCH = "WATCH"
    REVIEW_BUY = "REVIEW_BUY"
    REVIEW_SELL = "REVIEW_SELL"
    BLOCKED = "BLOCKED"


class ScoreComponent(BaseModel):
    """Single recommendation component score."""

    score: float | None = Field(default=None, ge=-1.0, le=1.0)
    label: str
    rationale: str


class RecommendationScores(BaseModel):
    """Transparent component scores used by a recommendation."""

    fundamental_valuation: ScoreComponent
    technical: ScoreComponent
    sentiment_news: ScoreComponent
    catalysts: ScoreComponent
    composite: float = Field(ge=-1.0, le=1.0)


class RecommendationCandidate(BaseModel):
    """Candidate security under review."""

    symbol: str
    research_symbol: str
    source: Literal["holding", "watchlist", "default"]
    name: str | None = None
    currency: str | None = None
    quantity: float = 0.0
    current_price: float | None = None
    current_value: float | None = None


class TradeRecommendation(BaseModel):
    """Recommendation row for one holding or market-scan candidate."""

    candidate: RecommendationCandidate
    action: RecommendationAction
    scores: RecommendationScores
    valuation: ValuationMetrics
    technicals: TechnicalIndicators
    upcoming_events: list[UpcomingEvent] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    sentiment: SentimentSnapshot | None = None
    risk_flags: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    llm_rationale: LLMRationaleResponse | None = None
    warnings: list[str] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    """Recommendation scan response."""

    status: str
    environment: str
    retrieved_at_utc: datetime
    provider: str
    recommendations: list[TradeRecommendation]
    warnings: list[str] = Field(default_factory=list)


def build_recommendations(
    snapshot: BrokerPortfolioSnapshot,
    *,
    candidates: Sequence[str] | None = None,
    include_default_candidates: bool = True,
    default_candidates: Sequence[str] | None = None,
    provider: ValuationProvider | None = None,
    as_of_utc: datetime | None = None,
    include_llm_rationale: bool = False,
) -> RecommendationsResponse:
    """Build review-only recommendations for holdings plus wider market candidates."""

    valuation_provider = provider or ODPScreenerValuationProvider()
    as_of = require_utc(as_of_utc or now_utc())
    recommendation_candidates = _recommendation_candidates(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_default_candidates,
        default_candidates=default_candidates,
    )
    research_symbols = sorted(
        {candidate.research_symbol for candidate in recommendation_candidates}
    )
    provider_data = valuation_provider.get_many(research_symbols) if research_symbols else {}
    warnings = list(snapshot.warnings)
    recommendations = [
        _recommend_candidate(
            candidate,
            provider_data.get(candidate.research_symbol),
            warnings,
            as_of,
            include_llm_rationale,
        )
        for candidate in recommendation_candidates
    ]
    recommendations.sort(
        key=lambda item: (
            _action_rank(item.action),
            -item.scores.composite,
            item.candidate.research_symbol,
        )
    )
    return RecommendationsResponse(
        status=snapshot.status,
        environment=snapshot.environment,
        retrieved_at_utc=require_utc(snapshot.retrieved_at_utc),
        provider=valuation_provider.name,
        recommendations=recommendations,
        warnings=warnings,
    )


def build_recommendations_from_static_data(
    snapshot: BrokerPortfolioSnapshot,
    data: Mapping[str, HoldingValuationData],
    *,
    candidates: Sequence[str] | None = None,
    include_default_candidates: bool = True,
    default_candidates: Sequence[str] | None = None,
    as_of_utc: datetime | None = None,
    include_llm_rationale: bool = False,
) -> RecommendationsResponse:
    """Convenience helper for deterministic offline tests and scripts."""

    return build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_default_candidates,
        default_candidates=default_candidates,
        provider=StaticValuationProvider(data),
        as_of_utc=as_of_utc,
        include_llm_rationale=include_llm_rationale,
    )


def _recommendation_candidates(
    snapshot: BrokerPortfolioSnapshot,
    *,
    candidates: Sequence[str] | None,
    include_default_candidates: bool,
    default_candidates: Sequence[str] | None,
) -> list[RecommendationCandidate]:
    rows: list[RecommendationCandidate] = []
    seen: set[str] = set()
    for position in snapshot.positions:
        research_symbol = research_symbol_for_position(position)
        rows.append(_candidate_from_position(position, research_symbol))
        seen.add(research_symbol.upper())

    watchlist = _normalise_symbols(candidates)
    if include_default_candidates:
        defaults = _normalise_symbols(default_candidates) or DEFAULT_MARKET_CANDIDATES
        watchlist.extend(symbol for symbol in defaults if symbol not in watchlist)

    for symbol in watchlist:
        key = symbol.upper()
        if key in seen:
            continue
        rows.append(
            RecommendationCandidate(
                symbol=symbol,
                research_symbol=symbol,
                source="default" if symbol in DEFAULT_MARKET_CANDIDATES else "watchlist",
            )
        )
        seen.add(key)
    return rows


def _candidate_from_position(
    position: BrokerPosition, research_symbol: str
) -> RecommendationCandidate:
    return RecommendationCandidate(
        symbol=position.symbol,
        research_symbol=research_symbol,
        source="holding",
        name=position.name,
        currency=position.currency,
        quantity=position.quantity,
        current_price=position.current_price,
        current_value=position.current_value,
    )


def _recommend_candidate(
    candidate: RecommendationCandidate,
    data: HoldingValuationData | None,
    response_warnings: list[str],
    as_of_utc: datetime,
    include_llm_rationale: bool,
) -> TradeRecommendation:
    warnings = list(data.warnings) if data else []
    if data is None:
        message = f"No valuation provider data for {candidate.research_symbol}."
        warnings.append(message)
        response_warnings.append(message)
        data = HoldingValuationData(symbol=candidate.research_symbol, retrieved_at_utc=now_utc())

    holding = HoldingValuation(
        symbol=candidate.symbol,
        broker_ticker=candidate.symbol,
        research_symbol=candidate.research_symbol,
        name=candidate.name,
        currency=candidate.currency,
        quantity=candidate.quantity,
        current_price=candidate.current_price,
        current_value=candidate.current_value,
        valuation=data.valuation,
        technicals=data.technicals or calculate_technicals(data.daily_adjusted_closes, warnings),
        upcoming_events=data.upcoming_events,
        news=data.news,
        sentiment=data.sentiment,
        warnings=warnings,
    )
    scores = _score_holding(holding, as_of_utc)
    risk_flags = _risk_flags(holding, scores, as_of_utc)
    action = _action_for(holding, scores, risk_flags)
    rationale = _rationale(holding, scores, action, risk_flags)
    llm_rationale = (
        _llm_rationale(holding, scores, action, risk_flags, rationale)
        if include_llm_rationale
        else None
    )
    return TradeRecommendation(
        candidate=candidate,
        action=action,
        scores=scores,
        valuation=holding.valuation,
        technicals=holding.technicals,
        upcoming_events=holding.upcoming_events,
        news=holding.news,
        sentiment=holding.sentiment,
        risk_flags=risk_flags,
        rationale=rationale,
        llm_rationale=llm_rationale,
        warnings=warnings,
    )


def _score_holding(holding: HoldingValuation, as_of_utc: datetime) -> RecommendationScores:
    fundamental = _fundamental_score(holding.valuation)
    technical = _technical_score(holding.technicals)
    sentiment = _sentiment_score(holding.sentiment, holding.news)
    catalysts = _catalyst_score(holding.upcoming_events, as_of_utc)
    values = [
        (fundamental.score, 0.40),
        (technical.score, 0.30),
        (sentiment.score, 0.15),
        (catalysts.score, 0.15),
    ]
    available = [(score, weight) for score, weight in values if score is not None]
    composite = (
        sum(score * weight for score, weight in available) / sum(weight for _, weight in available)
        if available
        else 0.0
    )
    return RecommendationScores(
        fundamental_valuation=fundamental,
        technical=technical,
        sentiment_news=sentiment,
        catalysts=catalysts,
        composite=_clamp(composite),
    )


def _fundamental_score(valuation: ValuationMetrics) -> ScoreComponent:
    inputs: list[float] = []
    if valuation.trailing_pe is not None and valuation.trailing_pe > 0:
        inputs.append(_scale_inverse(valuation.trailing_pe, cheap=12.0, expensive=35.0))
    if valuation.forward_pe is not None and valuation.forward_pe > 0:
        inputs.append(_scale_inverse(valuation.forward_pe, cheap=10.0, expensive=30.0))
    if valuation.price_to_book is not None and valuation.price_to_book > 0:
        inputs.append(_scale_inverse(valuation.price_to_book, cheap=1.2, expensive=5.0))
    if valuation.dividend_yield is not None:
        inputs.append(_scale_direct(valuation.dividend_yield, weak=0.0, strong=0.05))
    if not inputs:
        return ScoreComponent(
            score=None,
            label="unavailable",
            rationale="Fundamental and valuation inputs are unavailable.",
        )
    score = _average(inputs)
    return ScoreComponent(
        score=score,
        label=_score_label(score),
        rationale="Valuation uses available P/E, price/book, and dividend yield proxies.",
    )


def _technical_score(technicals: TechnicalIndicators) -> ScoreComponent:
    inputs = [
        value
        for value in [
            technicals.momentum_1m,
            technicals.momentum_3m,
            technicals.momentum_6m,
            technicals.momentum_12m,
        ]
        if value is not None
    ]
    if technicals.sma50 is not None and technicals.sma200 is not None and technicals.sma200 > 0:
        inputs.append((technicals.sma50 / technicals.sma200) - 1.0)
    if technicals.rsi14 is not None:
        inputs.append(_rsi_score(technicals.rsi14))
    if not inputs:
        return ScoreComponent(
            score=None,
            label="unavailable",
            rationale="Technical inputs are unavailable.",
        )
    score = _clamp(_average([_clamp(value * 4.0) for value in inputs]))
    return ScoreComponent(
        score=score,
        label=_score_label(score),
        rationale="Technical score uses momentum, trend, and RSI where available.",
    )


def _sentiment_score(
    sentiment: SentimentSnapshot | None, news: Sequence[NewsItem]
) -> ScoreComponent:
    if sentiment and sentiment.score is not None:
        score = _clamp(sentiment.score)
        return ScoreComponent(
            score=score,
            label=sentiment.label or _score_label(score),
            rationale="Sentiment score supplied by provider.",
        )
    if not news:
        return ScoreComponent(
            score=None,
            label="unavailable",
            rationale="No recent news or sentiment inputs are available.",
        )
    score = _clamp(len(news) / 10)
    return ScoreComponent(
        score=score,
        label="news_available",
        rationale="Recent news exists but has not been sentiment-scored.",
    )


def _catalyst_score(events: Sequence[UpcomingEvent], as_of_utc: datetime) -> ScoreComponent:
    if not events:
        return ScoreComponent(
            score=0.0,
            label="no_known_catalyst",
            rationale="No upcoming catalysts were supplied by the provider.",
        )
    blackout_events = [
        event for event in events if _is_blackout(_days_to_event(as_of_utc, event.ts_utc))
    ]
    if blackout_events:
        return ScoreComponent(
            score=-0.8,
            label="blackout",
            rationale="A known event falls inside the review blackout window.",
        )
    return ScoreComponent(
        score=0.2,
        label="catalyst_known",
        rationale="Known upcoming catalysts require human review but are outside blackout.",
    )


def _risk_flags(
    holding: HoldingValuation, scores: RecommendationScores, as_of_utc: datetime
) -> list[str]:
    flags: list[str] = []
    if holding.warnings:
        flags.append("DATA_WARNINGS")
    if scores.fundamental_valuation.score is None:
        flags.append("MISSING_FUNDAMENTALS")
    if scores.technical.score is None:
        flags.append("MISSING_TECHNICALS")
    if scores.sentiment_news.score is None:
        flags.append("MISSING_SENTIMENT")
    if any(
        _is_blackout(_days_to_event(as_of_utc, event.ts_utc)) for event in holding.upcoming_events
    ):
        flags.append("CATALYST_BLACKOUT")
    if holding.valuation.beta is not None and holding.valuation.beta >= 1.5:
        flags.append("HIGH_BETA")
    if holding.quantity > 0 and scores.composite <= -0.25:
        flags.append("HOLDING_SCORE_WEAK")
    return flags


def _action_for(
    holding: HoldingValuation,
    scores: RecommendationScores,
    risk_flags: Sequence[str],
) -> RecommendationAction:
    if "CATALYST_BLACKOUT" in risk_flags or not _has_minimum_data(scores):
        return RecommendationAction.BLOCKED
    if holding.quantity > 0:
        if scores.composite <= -0.35:
            return RecommendationAction.REVIEW_SELL
        return RecommendationAction.HOLD
    if scores.composite >= 0.35:
        return RecommendationAction.REVIEW_BUY
    return RecommendationAction.WATCH


def _has_minimum_data(scores: RecommendationScores) -> bool:
    return scores.fundamental_valuation.score is not None or scores.technical.score is not None


def _rationale(
    holding: HoldingValuation,
    scores: RecommendationScores,
    action: RecommendationAction,
    risk_flags: Sequence[str],
) -> list[str]:
    text = [
        f"{action.value} from composite score {scores.composite:.2f}.",
        scores.fundamental_valuation.rationale,
        scores.technical.rationale,
        scores.sentiment_news.rationale,
        scores.catalysts.rationale,
    ]
    if holding.quantity > 0:
        text.append("Existing holding: recommendation is review-only and does not submit orders.")
    else:
        text.append("Market-scan candidate: review-only watchlist signal.")
    if risk_flags:
        text.append(f"Risk flags: {', '.join(risk_flags)}.")
    return text


def _llm_rationale(
    holding: HoldingValuation,
    scores: RecommendationScores,
    action: RecommendationAction,
    risk_flags: Sequence[str],
    rationale: Sequence[str],
) -> LLMRationaleResponse:
    """Return optional LLM rationale for display, never for order generation."""

    return generate_llm_rationale(
        LLMRationaleRequest(
            symbol=holding.research_symbol,
            action=action.value,
            component_scores={
                "fundamental_valuation": scores.fundamental_valuation.score or 0.0,
                "technical": scores.technical.score or 0.0,
                "sentiment_news": scores.sentiment_news.score or 0.0,
                "catalysts": scores.catalysts.score or 0.0,
                "composite": scores.composite,
            },
            evidence=list(rationale),
            warnings=[*holding.warnings, *risk_flags],
        )
    )


def _normalise_symbols(symbols: Sequence[str] | None) -> list[str]:
    if not symbols:
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        for part in symbol.split(","):
            cleaned = part.strip()
            key = cleaned.upper()
            if cleaned and key not in seen:
                rows.append(cleaned)
                seen.add(key)
    return rows


def _days_to_event(as_of_utc: datetime, event_at_utc: datetime | None) -> int | None:
    if event_at_utc is None:
        return None
    return (require_utc(event_at_utc).date() - as_of_utc.date()).days


def _is_blackout(days_to_event: int | None) -> bool:
    if days_to_event is None:
        return False
    return -EVENT_BLACKOUT_DAYS_AFTER <= days_to_event <= EVENT_BLACKOUT_DAYS_BEFORE


def _scale_inverse(value: float, *, cheap: float, expensive: float) -> float:
    return _clamp(1.0 - (2.0 * ((value - cheap) / (expensive - cheap))))


def _scale_direct(value: float, *, weak: float, strong: float) -> float:
    return _clamp((2.0 * ((value - weak) / (strong - weak))) - 1.0)


def _rsi_score(rsi: float) -> float:
    if rsi >= 75:
        return -0.4
    if rsi <= 25:
        return 0.2
    return _clamp((rsi - 50.0) / 50.0)


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _score_label(score: float) -> str:
    if score >= 0.35:
        return "positive"
    if score <= -0.35:
        return "negative"
    return "neutral"


def _action_rank(action: RecommendationAction) -> int:
    return {
        RecommendationAction.REVIEW_BUY: 0,
        RecommendationAction.HOLD: 1,
        RecommendationAction.WATCH: 2,
        RecommendationAction.REVIEW_SELL: 3,
        RecommendationAction.BLOCKED: 4,
    }[action]


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))
