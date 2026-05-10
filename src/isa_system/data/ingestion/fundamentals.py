"""Fundamental ingestion helpers."""

from __future__ import annotations

import pandas as pd

from isa_system.data.schemas.pti import validate_pti_facts


def curate_fundamental_facts(raw: pd.DataFrame) -> pd.DataFrame:
    """Return validated point-in-time fundamental facts."""

    return validate_pti_facts(raw)
