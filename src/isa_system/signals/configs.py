"""Strategy config models."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from isa_system.utils.hashing import sha256_digest


class StrategyConfigModel(BaseModel):
    """Versioned strategy configuration."""

    name: str
    version: int = 1
    rebalance_frequency: str = "monthly"
    factor_weights: dict[str, float] = Field(default_factory=dict)
    hard_filters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    ranking: dict[str, object] = Field(default_factory=dict)
    target: dict[str, object] = Field(default_factory=dict)

    @property
    def config_hash(self) -> str:
        """Return a stable config hash."""

        return sha256_digest(self.model_dump(mode="json"))


def load_strategy_config(path: Path) -> StrategyConfigModel:
    """Load a YAML strategy config."""

    return StrategyConfigModel.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
