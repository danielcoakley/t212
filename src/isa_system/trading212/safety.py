"""Trading 212 safety helpers."""

from __future__ import annotations

LIVE_SUBMISSION_NOT_IMPLEMENTED = "Live Trading 212 order submission is not implemented."


def live_submission_available() -> bool:
    """Return whether live submission is available in this build."""

    return False
