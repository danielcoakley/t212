"""Optional X sentiment overlay, disabled by default."""

from __future__ import annotations

import pandas as pd

from isa_system.data.providers.base import empty_frame


class XSentimentProvider:
    """Return empty sentiment rows unless credentials and policy are configured."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def sentiment(self, symbols: list[str]) -> pd.DataFrame:
        """Return schema-valid optional sentiment rows."""

        _ = symbols
        return empty_frame(["symbol", "observed_at_utc", "score", "source_name", "warning"])
