"""OpenBB upstream and adapter routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from isa_system.openbb_adapter import (
    IsaOpenBBClient,
    OpenBBAdapterError,
    OpenBBUpstreamManager,
    dataframe_to_records,
)
from isa_system.settings import get_settings

router = APIRouter(prefix="/openbb", tags=["openbb"])


@router.get("/status")
def openbb_status() -> dict[str, object]:
    """Return the configured OpenBB/ODP backend and vendor checkout status."""

    status = OpenBBUpstreamManager().status()
    adapter_status = IsaOpenBBClient().status()
    return {
        **adapter_status,
        "vendor_path": str(status.vendor_path),
        "lock_path": str(status.lock_path),
        "current_revision": status.current_revision,
        "locked_revision": status.locked_revision,
        "remote_url": status.remote_url,
        "dirty": status.dirty,
        "matches_lock": status.matches_lock,
    }


@router.get("/compatibility/prices")
def openbb_price_compatibility(
    symbol: Annotated[str, Query(description="Sample symbol to fetch through OpenBB.")] = "AAPL",
    provider: Annotated[str, Query(description="OpenBB provider name.")] = "yfinance",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    """Run a small OpenBB adapter compatibility check."""

    try:
        frame = IsaOpenBBClient().equity_daily_prices(
            [symbol], start_date=start_date, end_date=end_date, provider=provider
        )
    except OpenBBAdapterError as exc:
        return {"status": "error", "symbol": symbol, "provider": provider, "error": str(exc)}
    return {
        "status": "ok",
        "symbol": symbol,
        "provider": provider,
        "rows": len(frame),
        "columns": list(frame.columns),
    }


@router.get("/search")
def openbb_equity_search(
    query: Annotated[str, Query(min_length=1, description="Ticker or company search text.")],
    provider: Annotated[str | None, Query(description="OpenBB provider name.")] = None,
) -> dict[str, object]:
    """Search OpenBB's equity universe through the app boundary."""

    provider_name = provider or get_settings().openbb_default_provider
    try:
        rows = IsaOpenBBClient().equity_search(query=query, provider=provider_name)
    except OpenBBAdapterError as exc:
        return {"status": "error", "query": query, "provider": provider_name, "error": str(exc)}
    return {"status": "ok", "query": query, "provider": provider_name, "results": rows}


@router.get("/ticker/{symbol}/profile")
def openbb_ticker_profile(
    symbol: str,
    provider: Annotated[str | None, Query(description="OpenBB provider name.")] = None,
) -> dict[str, object]:
    """Return OpenBB company profile rows for a ticker."""

    provider_name = provider or get_settings().openbb_default_provider
    try:
        rows = IsaOpenBBClient().equity_profile(symbol=symbol.upper(), provider=provider_name)
    except OpenBBAdapterError as exc:
        return {
            "status": "error",
            "symbol": symbol.upper(),
            "provider": provider_name,
            "error": str(exc),
        }
    return {
        "status": "ok",
        "symbol": symbol.upper(),
        "provider": provider_name,
        "profile": rows,
    }


@router.get("/ticker/{symbol}/context")
def openbb_ticker_context(
    symbol: str,
    provider: Annotated[str | None, Query(description="OpenBB provider name.")] = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    """Return a compact OpenBB company context bundle for the dashboard."""

    provider_name = provider or get_settings().openbb_default_provider
    client = IsaOpenBBClient()
    symbol_key = symbol.upper()
    errors: dict[str, str] = {}
    profile: list[dict[str, object]] = []
    fundamentals: list[dict[str, object]] = []
    price_summary: dict[str, object] = {
        "provider": provider_name,
        "rows": 0,
        "columns": [],
        "latest": None,
    }

    try:
        profile = client.equity_profile(symbol=symbol_key, provider=provider_name)
    except OpenBBAdapterError as exc:
        errors["profile"] = str(exc)

    try:
        fundamentals_frame = client.equity_fundamentals([symbol_key], provider=provider_name)
        fundamentals = dataframe_to_records(fundamentals_frame, limit=5)
    except OpenBBAdapterError as exc:
        errors["fundamentals"] = str(exc)

    try:
        price_frame = client.equity_daily_prices(
            [symbol_key], start_date=start_date, end_date=end_date, provider=provider_name
        )
        price_records = dataframe_to_records(price_frame.tail(1))
        price_summary = {
            "provider": provider_name,
            "rows": len(price_frame),
            "columns": list(price_frame.columns),
            "latest": price_records[0] if price_records else None,
        }
    except OpenBBAdapterError as exc:
        errors["prices"] = str(exc)

    status = "ok" if profile or fundamentals or price_summary["rows"] else "error"
    return {
        "status": status,
        "symbol": symbol_key,
        "provider": provider_name,
        "profile": profile,
        "fundamentals": fundamentals,
        "prices": price_summary,
        "errors": errors,
    }
