"""Raw provider payload schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from isa_system.utils.time import ensure_utc


class RawPayload(BaseModel):
    """Envelope for raw cached provider responses."""

    provider: str
    dataset: str
    retrieved_at_utc: datetime
    payload: Any = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        ensure_utc(self.retrieved_at_utc)
