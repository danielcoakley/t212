"""FCA National Storage Mechanism validation adapter.

TODO: Keep scraping or API usage aligned with the current FCA NSM public
terms and page structure. The starter treats NSM as archive validation,
not a real-time signal source.
"""

from __future__ import annotations

import pandas as pd

from isa_system.data.providers.base import empty_frame


class FCANSMProvider:
    """Validation-oriented placeholder for FCA NSM metadata."""

    def disclosures(self, query: str) -> pd.DataFrame:
        """Return schema-valid disclosure metadata."""

        _ = query
        return empty_frame(
            ["query", "headline", "event_date", "available_at_utc", "source_name", "url"]
        )
