"""Offline-safe valuation service for current ISA holdings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Protocol

import pandas as pd
from pydantic import BaseModel, Field

from isa_system.openbb_adapter import IsaOpenBBClient, OpenBBAdapterError
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc, require_utc


class DailyAdjustedClose(BaseModel):
    """Daily adjusted close used for technical indicators."""

    ts_utc: datetime
    adj_close: float


class TechnicalIndicators(BaseModel):
    """Technical indicators calculated from daily adjusted closes."""

    sma50: float | None = None
    sma200: float | None = None
    rsi14: float | None = None
    momentum_1m: float | None = None
    momentum_3m: float | None = None
    momentum_6m: float | None = None
    momentum_12m: float | None = None


class ValuationMetrics(BaseModel):
    """Point-in-time valuation metrics when available from a provider."""

    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    beta: float | None = None


class UpcomingEvent(BaseModel):
    """Provider-fed event placeholder for future earnings/dividend dates."""

    event_type: str
    ts_utc: datetime | None = None
    title: str | None = None
    source: str | None = None
    url: str | None = None


class NewsItem(BaseModel):
    """Provider-fed news placeholder for valuation context."""

    headline: str
    published_at_utc: datetime | None = None
    source: str | None = None
    url: str | None = None


class SentimentSnapshot(BaseModel):
    """Provider-fed sentiment placeholder for future enrichment."""

    label: str | None = None
    score: float | None = None
    source: str | None = None
    retrieved_at_utc: datetime | None = None


class HoldingValuationData(BaseModel):
    """Raw provider data for a single symbol."""

    symbol: str
    retrieved_at_utc: datetime
    daily_adjusted_closes: list[DailyAdjustedClose] = Field(default_factory=list)
    valuation: ValuationMetrics = Field(default_factory=ValuationMetrics)
    technicals: TechnicalIndicators | None = None
    upcoming_events: list[UpcomingEvent] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    sentiment: SentimentSnapshot | None = None
    warnings: list[str] = Field(default_factory=list)


class HoldingValuation(BaseModel):
    """Valuation row for a current broker holding."""

    symbol: str
    broker_ticker: str
    research_symbol: str
    name: str | None = None
    currency: str | None = None
    quantity: float
    current_price: float | None = None
    current_value: float | None = None
    valuation: ValuationMetrics
    technicals: TechnicalIndicators
    upcoming_events: list[UpcomingEvent]
    news: list[NewsItem]
    sentiment: SentimentSnapshot | None = None
    warnings: list[str]


class HoldingsValuationResponse(BaseModel):
    """Valuation response for the dashboard's live holdings view."""

    status: str
    environment: str
    retrieved_at_utc: datetime
    provider: str
    holdings: list[HoldingValuation]
    warnings: list[str]


class ValuationProvider(Protocol):
    """Provider protocol for optional valuation enrichment."""

    name: str

    def get_many(self, symbols: Sequence[str]) -> Mapping[str, HoldingValuationData]:
        """Return valuation data keyed by symbol."""


class StaticValuationProvider:
    """Deterministic provider for tests and offline fixtures."""

    name = "static"

    def __init__(self, data: Mapping[str, HoldingValuationData] | None = None) -> None:
        self._data = dict(data or {})

    def get_many(self, symbols: Sequence[str]) -> Mapping[str, HoldingValuationData]:
        """Return static data for requested symbols only."""

        return {symbol: self._data[symbol] for symbol in symbols if symbol in self._data}


class YFinanceValuationProvider:
    """Optional yfinance-backed provider that degrades to warnings offline."""

    name = "yfinance"

    def get_many(self, symbols: Sequence[str]) -> Mapping[str, HoldingValuationData]:
        """Fetch yfinance data, returning empty warning rows on provider failure."""

        try:
            import pandas as pd
            import yfinance as yf
        except ModuleNotFoundError:
            return {
                symbol: _empty_provider_data(symbol, "yfinance is not installed.")
                for symbol in symbols
            }

        rows: dict[str, HoldingValuationData] = {}
        for symbol in symbols:
            retrieved_at_utc = now_utc()
            warnings: list[str] = []
            closes: list[DailyAdjustedClose] = []
            valuation = ValuationMetrics()
            events: list[UpcomingEvent] = []
            news: list[NewsItem] = []
            try:
                ticker = yf.Ticker(symbol)
                history = ticker.history(period="18mo", interval="1d", auto_adjust=False)
                if history.empty:
                    warnings.append(f"No yfinance daily adjusted closes for {symbol}.")
                else:
                    close_col = "Adj Close" if "Adj Close" in history.columns else "Close"
                    history = history.reset_index()
                    date_col = "Date" if "Date" in history.columns else "Datetime"
                    closes = [
                        DailyAdjustedClose(
                            ts_utc=pd.to_datetime(row[date_col], utc=True).to_pydatetime(),
                            adj_close=float(row[close_col]),
                        )
                        for _, row in history.iterrows()
                        if pd.notna(row.get(close_col))
                    ]

                info = _safe_yfinance_info(ticker)
                if info:
                    valuation = ValuationMetrics(
                        trailing_pe=_float_or_none(info.get("trailingPE")),
                        forward_pe=_float_or_none(info.get("forwardPE")),
                        price_to_book=_float_or_none(info.get("priceToBook")),
                        dividend_yield=_normalise_dividend_yield(info.get("dividendYield")),
                        market_cap=_float_or_none(info.get("marketCap")),
                        beta=_float_or_none(info.get("beta")),
                    )
                else:
                    warnings.append(f"No yfinance valuation fields for {symbol}.")

                events = _safe_yfinance_events(ticker, symbol)
                news = _safe_yfinance_news(ticker)
            except Exception as exc:  # pragma: no cover - provider/network defensive path
                warnings.append(f"yfinance lookup failed for {symbol}: {exc.__class__.__name__}.")

            rows[symbol] = HoldingValuationData(
                symbol=symbol,
                retrieved_at_utc=retrieved_at_utc,
                daily_adjusted_closes=closes,
                valuation=valuation,
                upcoming_events=events,
                news=news,
                warnings=warnings,
            )
        return rows


class ODPScreenerValuationProvider:
    """ODP screener-backed provider for broad candidate valuation."""

    name = "openbb-odp-screener"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: IsaOpenBBClient | None = None,
        screener_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._screener_rows = [dict(row) for row in screener_rows] if screener_rows else None

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def client(self) -> IsaOpenBBClient:
        if self._client is None:
            self._client = IsaOpenBBClient(settings=self.settings)
        return self._client

    def get_many(self, symbols: Sequence[str]) -> Mapping[str, HoldingValuationData]:
        """Return valuation data from ODP screener rows, with ODP detail fallback."""

        symbols_by_key = {symbol.upper(): symbol for symbol in symbols}
        rows = self._rows_for_symbols(symbols)
        rows_by_key = {
            str(row.get("symbol") or row.get("ticker") or "").upper(): row for row in rows
        }
        data: dict[str, HoldingValuationData] = {}
        for key, requested_symbol in symbols_by_key.items():
            row = rows_by_key.get(key)
            if row is not None:
                data[requested_symbol] = _odp_screener_row_to_data(requested_symbol, row)
                continue
            data[requested_symbol] = self._detail_fallback(requested_symbol)
        return data

    def _rows_for_symbols(self, symbols: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        if self._screener_rows is not None:
            return self._screener_rows
        limit = max(len(symbols) * 2, 50)
        try:
            return self.client.equity_screener(
                provider=self.settings.openbb_screener_provider,
                country=self.settings.openbb_screener_country,
                exchange=self.settings.openbb_screener_exchange,
                mktcap_min=self.settings.openbb_screener_market_cap_min,
                volume_min=self.settings.openbb_screener_volume_min,
                limit=limit,
            )
        except OpenBBAdapterError:
            return []

    def _detail_fallback(self, symbol: str) -> HoldingValuationData:
        warnings: list[str] = []
        valuation = ValuationMetrics()
        closes: list[DailyAdjustedClose] = []
        retrieved_at = now_utc()
        try:
            fundamentals = self.client.equity_fundamentals(
                [symbol], provider=self.settings.openbb_default_provider
            )
            if not fundamentals.empty:
                valuation = _valuation_from_mapping(fundamentals.iloc[0].to_dict())
        except OpenBBAdapterError as exc:
            warnings.append(f"ODP fundamentals unavailable for {symbol}: {exc}")
        try:
            prices = self.client.equity_daily_prices(
                [symbol], provider=self.settings.openbb_default_provider
            )
            closes = [
                DailyAdjustedClose(
                    ts_utc=require_utc(row["ts_utc"].to_pydatetime()),
                    adj_close=float(row["adj_close"]),
                )
                for _, row in prices.iterrows()
                if pd.notna(row.get("adj_close"))
            ]
        except OpenBBAdapterError as exc:
            warnings.append(f"ODP price history unavailable for {symbol}: {exc}")
        if not closes and valuation == ValuationMetrics():
            warnings.append(f"No ODP screener row for {symbol}.")
        return HoldingValuationData(
            symbol=symbol,
            retrieved_at_utc=retrieved_at,
            daily_adjusted_closes=closes,
            valuation=valuation,
            warnings=warnings,
        )


def _odp_screener_row_to_data(symbol: str, row: Mapping[str, Any]) -> HoldingValuationData:
    """Convert one ODP screener row into recommendation valuation inputs."""

    return HoldingValuationData(
        symbol=symbol,
        retrieved_at_utc=now_utc(),
        valuation=_valuation_from_mapping(row),
        technicals=TechnicalIndicators(
            sma50=_float_or_none(row.get("ma50") or row.get("sma50")),
            sma200=_float_or_none(row.get("ma200") or row.get("sma200")),
        ),
    )


def _valuation_from_mapping(row: Mapping[str, Any]) -> ValuationMetrics:
    """Map common ODP screener/fundamental field names into local valuation metrics."""

    return ValuationMetrics(
        trailing_pe=_float_or_none(
            row.get("pe_ratio")
            or row.get("price_to_earnings")
            or row.get("trailing_pe")
            or row.get("trailingPE")
        ),
        forward_pe=_float_or_none(
            row.get("pe_forward") or row.get("forward_pe") or row.get("forwardPE")
        ),
        price_to_book=_float_or_none(row.get("price_to_book") or row.get("priceToBook")),
        dividend_yield=_normalise_dividend_yield(row.get("dividend_yield")),
        market_cap=_float_or_none(row.get("market_cap") or row.get("marketCap")),
        beta=_float_or_none(row.get("beta")),
    )


def value_current_holdings(
    snapshot: BrokerPortfolioSnapshot, provider: ValuationProvider | None = None
) -> HoldingsValuationResponse:
    """Build valuation rows for the broker snapshot's current holdings."""

    valuation_provider = provider or YFinanceValuationProvider()
    symbol_map = {
        position.symbol: research_symbol_for_position(position) for position in snapshot.positions
    }
    research_symbols = sorted(set(symbol_map.values()))
    provider_data = valuation_provider.get_many(research_symbols) if research_symbols else {}
    warnings = list(snapshot.warnings)
    holdings = [
        _value_position(
            position,
            symbol_map[position.symbol],
            provider_data.get(symbol_map[position.symbol]),
            warnings,
        )
        for position in snapshot.positions
    ]
    return HoldingsValuationResponse(
        status=snapshot.status,
        environment=snapshot.environment,
        retrieved_at_utc=require_utc(snapshot.retrieved_at_utc),
        provider=valuation_provider.name,
        holdings=holdings,
        warnings=warnings,
    )


def calculate_technicals(
    closes: Sequence[DailyAdjustedClose], warnings: list[str] | None = None
) -> TechnicalIndicators:
    """Calculate technical indicators from sorted daily adjusted closes."""

    sorted_closes = sorted(closes, key=lambda item: require_utc(item.ts_utc))
    values = [item.adj_close for item in sorted_closes if item.adj_close > 0]
    notes = warnings if warnings is not None else []
    if not values:
        notes.append("Daily adjusted closes are missing; technical indicators are unavailable.")
        return TechnicalIndicators()

    return TechnicalIndicators(
        sma50=_sma(values, 50, notes),
        sma200=_sma(values, 200, notes),
        rsi14=_rsi(values, 14, notes),
        momentum_1m=_momentum(values, 21),
        momentum_3m=_momentum(values, 63),
        momentum_6m=_momentum(values, 126),
        momentum_12m=_momentum(values, 252),
    )


def research_symbol_for_position(position: BrokerPosition) -> str:
    """Map common Trading 212 platform tickers to research-feed symbols.

    Trading 212 is the execution/account source of truth, but convenience data
    feeds such as yfinance use their own symbol grammar. This helper keeps the
    mapping explicit and conservative; anything uncertain falls back to the
    broker ticker stripped of the generic equity suffix.
    """

    candidate = (position.symbol or position.broker_ticker).strip()
    if candidate.endswith(".L") or candidate.endswith(".IL"):
        return candidate

    upper = candidate.upper()
    if upper.endswith("_US_EQ"):
        return candidate[: -len("_US_EQ")]
    if upper.endswith("_GB_EQ") or upper.endswith("_LSE_EQ"):
        return f"{candidate.rsplit('_', 2)[0]}.L"
    if candidate.endswith("l_EQ") or candidate.endswith("L_EQ"):
        return f"{candidate[:-4]}.L"
    if upper.endswith("_EQ"):
        stripped = candidate[:-3]
        if (position.currency or "").upper() in {"GBP", "GBX"}:
            return f"{stripped}.L"
        return stripped
    return candidate


def _value_position(
    position: BrokerPosition,
    research_symbol: str,
    data: HoldingValuationData | None,
    response_warnings: list[str],
) -> HoldingValuation:
    """Merge broker holdings with provider valuation data."""

    warnings = list(data.warnings) if data else []
    if data is None:
        message = f"No valuation provider data for {research_symbol}."
        warnings.append(message)
        response_warnings.append(message)
        data = _empty_provider_data(research_symbol)
    valuation_warnings = _missing_valuation_warnings(research_symbol, data.valuation)
    warnings.extend(valuation_warnings)
    technicals = data.technicals or calculate_technicals(data.daily_adjusted_closes, warnings)

    return HoldingValuation(
        symbol=position.symbol,
        broker_ticker=position.broker_ticker,
        research_symbol=research_symbol,
        name=position.name,
        currency=position.currency,
        quantity=position.quantity,
        current_price=position.current_price,
        current_value=position.current_value,
        valuation=data.valuation,
        technicals=technicals,
        upcoming_events=data.upcoming_events,
        news=data.news,
        sentiment=data.sentiment,
        warnings=warnings,
    )


def _empty_provider_data(symbol: str, warning: str | None = None) -> HoldingValuationData:
    """Create an empty provider row with an optional warning."""

    return HoldingValuationData(
        symbol=symbol,
        retrieved_at_utc=now_utc(),
        warnings=[warning] if warning else [],
    )


def _sma(values: Sequence[float], window: int, warnings: list[str]) -> float | None:
    """Return a simple moving average when enough closes exist."""

    if len(values) < window:
        warnings.append(
            f"Need {window} daily closes for SMA{window}; only {len(values)} available."
        )
        return None
    return sum(values[-window:]) / window


def _rsi(values: Sequence[float], period: int, warnings: list[str]) -> float | None:
    """Return simple RSI using the most recent period of daily changes."""

    if len(values) <= period:
        warnings.append(
            f"Need {period + 1} daily closes for RSI{period}; only {len(values)} available."
        )
        return None
    deltas = [
        current - previous
        for previous, current in zip(values[-period - 1 : -1], values[-period:], strict=True)
    ]
    gains = [delta for delta in deltas if delta > 0]
    losses = [-delta for delta in deltas if delta < 0]
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _momentum(values: Sequence[float], periods: int) -> float | None:
    """Return percentage change over an approximate trading-day lookback."""

    if len(values) <= periods:
        return None
    start = values[-periods - 1]
    if start <= 0:
        return None
    return (values[-1] / start) - 1


def _missing_valuation_warnings(symbol: str, valuation: ValuationMetrics) -> list[str]:
    """Describe missing valuation fields without failing the request."""

    missing = [field_name for field_name, value in valuation.model_dump().items() if value is None]
    if not missing:
        return []
    return [f"Missing valuation fields for {symbol}: {', '.join(missing)}."]


def _safe_yfinance_info(ticker: object) -> Mapping[str, object]:
    """Read yfinance info without letting provider issues escape."""

    try:
        info = getattr(ticker, "info", None)
    except Exception:
        return {}
    return info if isinstance(info, Mapping) else {}


def _safe_yfinance_news(ticker: object) -> list[NewsItem]:
    """Read a small yfinance news sample when available."""

    try:
        raw_news = getattr(ticker, "news", None) or []
    except Exception:
        return []
    items: list[NewsItem] = []
    for item in raw_news[:5]:
        if not isinstance(item, Mapping):
            continue
        raw_content = item.get("content")
        content: Mapping[str, Any] = raw_content if isinstance(raw_content, Mapping) else item
        headline = content.get("title") or content.get("headline")
        if not headline:
            continue
        published = _datetime_from_epoch(
            content.get("pubDate") or content.get("providerPublishTime")
        )
        items.append(
            NewsItem(
                headline=str(headline),
                published_at_utc=published,
                source=_string_or_none(content.get("provider") or content.get("publisher")),
                url=_string_or_none(content.get("canonicalUrl") or content.get("link")),
            )
        )
    return items


def _safe_yfinance_events(ticker: object, symbol: str) -> list[UpcomingEvent]:
    """Read yfinance calendar events when available."""

    try:
        calendar = getattr(ticker, "calendar", None)
    except Exception:
        return []
    if calendar is None:
        return []

    events: list[UpcomingEvent] = []
    try:
        items = calendar.items() if isinstance(calendar, Mapping) else calendar.to_dict().items()
    except Exception:
        return []
    for key, value in items:
        event_time = _coerce_event_datetime(value)
        if event_time is None:
            continue
        events.append(
            UpcomingEvent(
                event_type=str(key),
                ts_utc=event_time,
                title=f"{symbol} {key}",
                source="yfinance",
            )
        )
    return events


def _coerce_event_datetime(value: object) -> datetime | None:
    """Coerce common yfinance calendar date shapes to UTC datetimes."""

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        values = list(value)
        value = values[0] if values else None
    if isinstance(value, datetime):
        event_time = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return require_utc(event_time)
    try:
        import pandas as pd

        parsed = pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return None
    if parsed is None or bool(pd.isna(parsed)):
        return None
    return parsed.to_pydatetime()


def _datetime_from_epoch(value: object) -> datetime | None:
    """Coerce epoch seconds or ISO-like strings to a UTC datetime."""

    if value is None:
        return None
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, tz=UTC)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        parsed = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        return require_utc(parsed)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    """Coerce provider numeric values defensively."""

    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _normalise_dividend_yield(value: object) -> float | None:
    """Normalise yfinance dividend yield to decimal form when plausible."""

    parsed = _float_or_none(value)
    if parsed is None:
        return None
    return parsed / 100 if parsed > 1 else parsed


def _string_or_none(value: object) -> str | None:
    """Return a string for non-empty provider values."""

    if value is None:
        return None
    text = str(value)
    return text or None
