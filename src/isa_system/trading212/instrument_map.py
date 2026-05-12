"""Broker symbol mapping helpers."""

from __future__ import annotations


def broker_ticker_to_symbol(ticker: str) -> str:
    """Map a Trading 212 ticker-ish value to a research symbol best effort."""

    return ticker.removesuffix("_EQ").replace("l", ".L").upper()


def symbol_to_broker_ticker(symbol: str) -> str:
    """Map a research symbol to a placeholder broker ticker for previews."""

    if symbol.endswith(".L"):
        return f"{symbol.removesuffix('.L').lower()}_EQ"
    return f"{symbol}_EQ"
