"""Check local OpenBB API availability without requiring API keys."""

from __future__ import annotations

import sys

import httpx

from isa_system.settings import get_settings


def check_url(client: httpx.Client, url: str) -> bool:
    """Return whether a URL responds successfully and print a clear status line."""

    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"FAIL {url} - {exc}")
        return False
    print(f"PASS {url}")
    return True


def main() -> int:
    """Check the OpenBB OpenAPI and widget metadata endpoints."""

    settings = get_settings()
    base_url = settings.openbb_api_url.rstrip("/")
    urls = [f"{base_url}/openapi.json", f"{base_url}/widgets.json"]
    with httpx.Client(timeout=5.0, follow_redirects=True) as client:
        results = [check_url(client, url) for url in urls]
    if all(results):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
