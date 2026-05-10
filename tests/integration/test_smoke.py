"""Smoke-test integration."""

from __future__ import annotations

from pathlib import Path

from isa_system.smoke_test import run_smoke_test


def test_smoke_outputs(tmp_path: Path) -> None:
    """Synthetic smoke test writes required artifacts."""

    paths = run_smoke_test(tmp_path)
    for path in paths.values():
        assert path.exists()
    assert (tmp_path / "metrics.csv").exists()
    assert (tmp_path / "trades.csv").exists()
    assert (tmp_path / "holdings.csv").exists()
    assert (tmp_path / "rebalance_preview.json").exists()
