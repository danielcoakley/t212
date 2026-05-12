"""Models for Finviz discovery and candidate intake."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FinvizScreenerConfig(BaseModel):
    """Curated Finviz screener definition."""

    model_config = ConfigDict(extra="forbid")

    name: str
    purpose: str
    url: HttpUrl


class Candidate(BaseModel):
    """A normalized candidate discovered by one or more screeners."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    source_screener: str
    discovered_at_utc: datetime
    screener_rank: int | None = None
    raw_fields: dict[str, str] = Field(default_factory=dict)
    cache_key: str
    source_screeners: list[str] = Field(default_factory=list)
    screener_appearance_count: int = 1
    multi_screener_boost: float = 0.0


class CandidateDiscoveryResult(BaseModel):
    """Result from a candidate discovery run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    discovered_at_utc: datetime
    candidates: list[Candidate]
    warnings: list[str] = Field(default_factory=list)


class ParsedFinvizRow(BaseModel):
    """A parsed Finviz row before candidate normalization."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    rank: int | None = None
    raw_fields: dict[str, str] = Field(default_factory=dict)
    profile_url: str | None = None
