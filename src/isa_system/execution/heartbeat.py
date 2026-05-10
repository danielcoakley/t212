"""Subsystem heartbeat checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from isa_system.utils.time import now_utc


@dataclass(frozen=True)
class HeartbeatStatus:
    """Heartbeat result."""

    subsystem: str
    ok: bool
    checked_at_utc: datetime
    message: str


def ok(subsystem: str, message: str = "ok") -> HeartbeatStatus:
    """Return a successful heartbeat."""

    return HeartbeatStatus(subsystem=subsystem, ok=True, checked_at_utc=now_utc(), message=message)
