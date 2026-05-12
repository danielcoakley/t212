"""Polite Finviz fetcher with local HTML caching."""

from __future__ import annotations

from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from isa_system.discovery.models import FinvizScreenerConfig
from isa_system.utils.hashing import sha256_digest

POLITE_FINVIZ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; isa-system-local-research/0.1; +https://localhost.invalid)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.8",
}


class FinvizFetcher:
    """Fetch Finviz screener HTML conservatively and cache each response."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.timeout_seconds = timeout_seconds
        self.client = client
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_key(self, screener: FinvizScreenerConfig) -> str:
        """Return the stable cache key for a screener URL."""

        return sha256_digest({"name": screener.name, "url": str(screener.url)})

    def cache_path(self, screener: FinvizScreenerConfig) -> Path:
        """Return the local cache path for a screener."""

        return self.cache_dir / f"{self.cache_key(screener)}.html"

    def fetch(self, screener: FinvizScreenerConfig, *, force_refresh: bool = False) -> str:
        """Fetch a screener page, reusing cached HTML unless refresh is requested."""

        cache_path = self.cache_path(screener)
        if cache_path.exists() and not force_refresh:
            return cache_path.read_text(encoding="utf-8")

        html = self._fetch_url(str(screener.url))
        cache_path.write_text(html, encoding="utf-8")
        return html

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _fetch_url(self, url: str) -> str:
        """Fetch one URL with retry/backoff for transient network failures."""

        if self.client is not None:
            response = self.client.get(
                url, headers=POLITE_FINVIZ_HEADERS, timeout=self.timeout_seconds
            )
            response.raise_for_status()
            return response.text

        with httpx.Client(follow_redirects=True) as client:
            response = client.get(
                url,
                headers=POLITE_FINVIZ_HEADERS,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.text
