"""Audit routes."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.services.audit_status import AuditStatusSnapshot, load_audit_status

router = APIRouter()


@router.get("/audit", response_model=AuditStatusSnapshot)
def audit() -> AuditStatusSnapshot:
    """Return local audit and operator status."""

    return load_audit_status()
