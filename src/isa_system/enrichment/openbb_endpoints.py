"""Centralized OpenBB API endpoint definitions.

These paths are intentionally isolated because OpenBB API routes can vary by
version/provider installation. Callers should refer to endpoint keys instead of
hard-coding paths throughout the codebase.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OpenBBEndpoint(BaseModel):
    """Definition for one attempted OpenBB section."""

    model_config = ConfigDict(extra="forbid")

    section: str
    path: str
    params: dict[str, str] | None = None


OPENBB_ENDPOINTS: dict[str, OpenBBEndpoint] = {
    "price_history": OpenBBEndpoint(
        section="price_history",
        path="/api/v1/equity/price/historical",
        params={"provider": "yfinance"},
    ),
    "company_profile": OpenBBEndpoint(
        section="company_profile",
        path="/api/v1/equity/profile",
        params={"provider": "yfinance"},
    ),
    "fundamentals": OpenBBEndpoint(
        section="fundamentals",
        path="/api/v1/equity/fundamental/income",
        params={"provider": "yfinance"},
    ),
    "ratios": OpenBBEndpoint(
        section="ratios",
        path="/api/v1/equity/fundamental/ratios",
        params={"provider": "yfinance"},
    ),
    "earnings": OpenBBEndpoint(
        section="earnings",
        path="/api/v1/equity/calendar/earnings",
        params={"provider": "yfinance"},
    ),
    "news": OpenBBEndpoint(
        section="news",
        path="/api/v1/news/company",
        params={"provider": "benzinga"},
    ),
    "filings": OpenBBEndpoint(
        section="filings",
        path="/api/v1/equity/fundamental/filings",
        params={"provider": "sec"},
    ),
    "technicals": OpenBBEndpoint(
        section="technicals",
        path="/api/v1/technical/ema",
        params={"provider": "finta"},
    ),
}
