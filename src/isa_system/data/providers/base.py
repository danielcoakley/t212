"""Common provider protocols and safe failure types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider that needs credentials is called without them."""


@dataclass(frozen=True)
class ProviderRateLimit:
    """Simple rate-limit settings."""

    requests: int
    period_seconds: int


@dataclass(frozen=True)
class ProviderConfig:
    """Base provider configuration."""

    name: str
    cache_path: Path
    api_key: str | None = None
    rate_limit: ProviderRateLimit = ProviderRateLimit(requests=1, period_seconds=1)


class PriceProvider(Protocol):
    """Protocol for research price providers."""

    def daily_prices(self, symbols: list[str]) -> pd.DataFrame:
        """Return daily price rows."""


def empty_frame(columns: list[str]) -> pd.DataFrame:
    """Return a schema-valid empty DataFrame."""

    return pd.DataFrame(columns=columns)
