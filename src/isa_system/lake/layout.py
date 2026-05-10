"""Partitioned Parquet lake layout helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path


class LakeLayout:
    """Build canonical data lake paths."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def raw_path(self, provider: str, dataset: str, day: date) -> Path:
        """Return a raw partition path."""

        return (
            self.root
            / "raw"
            / f"provider={provider}"
            / f"dataset={dataset}"
            / f"date={day.isoformat()}"
        )

    def curated_path(self, provider: str, dataset: str, symbol: str, year: int) -> Path:
        """Return a curated partition path."""

        return (
            self.root
            / "curated"
            / f"provider={provider}"
            / f"dataset={dataset}"
            / f"symbol={symbol}"
            / f"year={year}"
        )

    def derived_factors_path(self, strategy: str) -> Path:
        """Return a derived factor path."""

        return self.root / "derived" / "factors" / f"strategy={strategy}"
