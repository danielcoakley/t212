"""OpenBB API wrapper with per-run cache and graceful errors."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from isa_system.enrichment.openbb_endpoints import OPENBB_ENDPOINTS, OpenBBEndpoint
from isa_system.settings import Settings, get_settings


class OpenBBSectionResult(BaseModel):
    """Structured result for one OpenBB section request."""

    model_config = ConfigDict(extra="forbid")

    section: str
    endpoint: str
    status: str
    data: Any | None = None
    error: str | None = None


class OpenBBHealth(BaseModel):
    """OpenBB availability status."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    base_url: str
    openapi: str
    widgets: str
    error: str | None = None


class OpenBBClient:
    """Small OpenBB HTTP client wrapper used by enrichment services."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = (base_url or self.settings.openbb_api_url).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client
        self._cache: dict[tuple[str, str], OpenBBSectionResult] = {}

    def health_check(self) -> OpenBBHealth:
        """Check OpenBB OpenAPI and widget metadata endpoints."""

        try:
            openapi_ok = self._simple_get("/openapi.json")
            widgets_ok = self._simple_get("/widgets.json")
        except httpx.HTTPError as exc:
            return OpenBBHealth(
                available=False,
                base_url=self.base_url,
                openapi="unavailable",
                widgets="unavailable",
                error=str(exc),
            )

        return OpenBBHealth(
            available=openapi_ok and widgets_ok,
            base_url=self.base_url,
            openapi="ok" if openapi_ok else "unavailable",
            widgets="ok" if widgets_ok else "unavailable",
        )

    def get_section(self, section: str, symbol: str) -> OpenBBSectionResult:
        """Fetch one configured OpenBB section for a symbol."""

        endpoint = OPENBB_ENDPOINTS[section]
        key = (section, symbol.upper())
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        result = self._request_section(endpoint, symbol.upper())
        self._cache[key] = result
        return result

    def _request_section(self, endpoint: OpenBBEndpoint, symbol: str) -> OpenBBSectionResult:
        params = {"symbol": symbol}
        if endpoint.params:
            params.update(endpoint.params)

        try:
            response = self._client_get(endpoint.path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return OpenBBSectionResult(
                section=endpoint.section,
                endpoint=endpoint.path,
                status="missing",
                error=f"HTTP {exc.response.status_code}",
            )
        except httpx.HTTPError as exc:
            return OpenBBSectionResult(
                section=endpoint.section,
                endpoint=endpoint.path,
                status="unavailable",
                error=str(exc),
            )

        try:
            data = response.json()
        except ValueError:
            return OpenBBSectionResult(
                section=endpoint.section,
                endpoint=endpoint.path,
                status="missing",
                error="response was not JSON",
            )

        status = "missing" if data in ({}, [], None) else "ok"
        return OpenBBSectionResult(
            section=endpoint.section,
            endpoint=endpoint.path,
            status=status,
            data=data,
        )

    def _simple_get(self, path: str) -> bool:
        response = self._client_get(path, params=None)
        return 200 <= response.status_code < 300

    def _client_get(self, path: str, params: dict[str, str] | None) -> httpx.Response:
        url = f"{self.base_url}{path}"
        if self.client is not None:
            return self.client.get(url, params=params, timeout=self.timeout_seconds)
        with httpx.Client(follow_redirects=True) as client:
            return client.get(url, params=params, timeout=self.timeout_seconds)
