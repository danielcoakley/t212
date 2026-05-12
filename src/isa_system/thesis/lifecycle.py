"""Thesis lifecycle helpers."""

from __future__ import annotations

from typing import ClassVar

from isa_system.thesis.models import Thesis, ThesisStatus


class ThesisLifecycleService:
    """Small lifecycle helper for watchlist and active thesis views."""

    watchlist_statuses: ClassVar[set[ThesisStatus]] = {
        ThesisStatus.WATCHLIST_WAIT_ENTRY,
        ThesisStatus.WATCHLIST_WAIT_CATALYST,
        ThesisStatus.NEEDS_REVIEW,
    }
    active_statuses: ClassVar[set[ThesisStatus]] = {ThesisStatus.ACTIVE_HOLDING}

    def is_watchlist(self, thesis: Thesis) -> bool:
        """Return whether a thesis belongs on the watchlist."""

        return thesis.status in self.watchlist_statuses
