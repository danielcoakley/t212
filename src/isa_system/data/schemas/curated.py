"""Curated table schemas for prices and facts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from isa_system.utils.time import ensure_utc


class PriceBarRecord(BaseModel):
    """Curated price bar row."""

    symbol: str
    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float
    source: str

    def model_post_init(self, __context: object) -> None:
        ensure_utc(self.ts_utc)


class CuratedFactRecord(BaseModel):
    """Curated point-in-time fact row."""

    symbol: str
    fact_name: str
    value: float | str | None
    available_at_utc: datetime
    source_name: str

    def model_post_init(self, __context: object) -> None:
        ensure_utc(self.available_at_utc)
