"""Broker reconciliation helpers."""

from __future__ import annotations


def compare_positions(
    expected: dict[str, float], actual: dict[str, float], tolerance: float = 1e-6
) -> dict[str, float]:
    """Return position differences larger than tolerance."""

    diffs = {}
    for symbol in sorted(set(expected) | set(actual)):
        diff = actual.get(symbol, 0.0) - expected.get(symbol, 0.0)
        if abs(diff) > tolerance:
            diffs[symbol] = diff
    return diffs
