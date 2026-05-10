"""CRUD helpers for audit logs and idempotency."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from isa_system.db.models import AuditLog, IdempotencyKey
from isa_system.utils.hashing import sha256_digest


def append_audit_log(
    session: Session, *, actor: str, action: str, payload: Any, outcome: str
) -> AuditLog:
    """Append an audit log row with a previous-hash chain."""

    previous = session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    previous_hash = previous.payload_hash if previous else None
    row = AuditLog(
        actor=actor,
        action=action,
        payload_hash=sha256_digest({"payload": payload, "previous_hash": previous_hash}),
        previous_hash=previous_hash,
        outcome=outcome,
    )
    session.add(row)
    session.flush()
    return row


def reserve_idempotency_key(
    session: Session, *, key: str, payload_hash: str, order_batch_id: str | None = None
) -> bool:
    """Reserve an idempotency key, returning False on duplicate."""

    row = IdempotencyKey(key=key, payload_hash=payload_hash, order_batch_id=order_batch_id)
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return False
    return True


def idempotency_key_exists(session: Session, key: str) -> bool:
    """Return whether an idempotency key already exists."""

    return session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key)) is not None
