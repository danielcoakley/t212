"""Curated Finviz screener configuration loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from isa_system.discovery.models import FinvizScreenerConfig

DEFAULT_FINVIZ_CONFIG_PATH = Path("configs/finviz_screeners.yaml")


def load_finviz_screeners(path: Path = DEFAULT_FINVIZ_CONFIG_PATH) -> list[FinvizScreenerConfig]:
    """Load curated Finviz screener definitions from YAML."""

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    screeners = payload.get("screeners", [])
    return [FinvizScreenerConfig.model_validate(screener) for screener in screeners]
