"""Base factor types."""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class FactorCalculator(Protocol):
    """Protocol for factor calculators."""

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """Compute factor values."""
