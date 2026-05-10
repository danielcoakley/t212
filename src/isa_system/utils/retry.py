"""Retry policy helpers for safe provider reads."""

from __future__ import annotations

from collections.abc import Callable

from tenacity import retry, stop_after_attempt, wait_exponential_jitter


def provider_read_retry[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Retry idempotent provider reads with conservative backoff."""

    return retry(wait=wait_exponential_jitter(initial=1, max=8), stop=stop_after_attempt(3))(func)
