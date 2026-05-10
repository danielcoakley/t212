"""Enumerations for domain and control-plane state."""

from __future__ import annotations

from enum import StrEnum


class RuntimeMode(StrEnum):
    """Supported execution modes."""

    PREVIEW = "preview"
    PAPER = "paper"
    LIVE = "live"


class AssetType(StrEnum):
    """Asset types allowed in the starter domain."""

    STOCK = "STOCK"
    ETF = "ETF"


class OrderType(StrEnum):
    """Broker order types used by the starter."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(StrEnum):
    """Buy or sell side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    """Internal and broker order states."""

    PREVIEW = "PREVIEW"
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class TimestampPrecision(StrEnum):
    """Precision of a source timestamp."""

    EXACT = "exact"
    DATE = "date"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class RebalanceStatus(StrEnum):
    """Rebalance run state."""

    PREVIEWED = "PREVIEWED"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
