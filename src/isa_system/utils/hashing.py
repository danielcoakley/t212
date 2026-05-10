"""Canonical hashing helpers for configs, audit payloads, and idempotency."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any


def canonical_json(payload: Any) -> str:
    """Serialise a payload deterministically."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_digest(payload: Any) -> str:
    """Return a SHA-256 hex digest for a canonical payload."""

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def make_idempotency_key(
    *,
    strategy_run_id: str,
    environment: str,
    payload: Any,
    trading_date: date,
) -> str:
    """Create a local idempotency key for broker order submissions."""

    envelope = {
        "strategy_run_id": strategy_run_id,
        "environment": environment,
        "trading_date": trading_date.isoformat(),
        "payload_hash": sha256_digest(payload),
    }
    return sha256_digest(envelope)
