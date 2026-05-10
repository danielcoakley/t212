"""Simple file catalogue for Parquet datasets."""

from __future__ import annotations

from pathlib import Path


def list_parquet_files(root: Path) -> list[Path]:
    """List Parquet files in the lake."""

    if not root.exists():
        return []
    return sorted(root.rglob("*.parquet"))
