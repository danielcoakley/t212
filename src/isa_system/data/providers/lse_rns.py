"""LSE RNS validation adapter.

TODO: Public RNS pages and payloads should be validated against the
current permitted access route before expanding this beyond safe empty
or manually supplied metadata.
"""

from __future__ import annotations

import pandas as pd

from isa_system.data.providers.base import empty_frame


class LSERNSProvider:
    """Validation-oriented placeholder for LSE RNS metadata."""

    def announcements(self, symbols: list[str]) -> pd.DataFrame:
        """Return schema-valid announcement metadata."""

        _ = symbols
        return empty_frame(
            ["symbol", "event_type", "event_date", "available_at_utc", "source_name", "url"]
        )
