"""Order lookup routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/orders/batches/{batch_id}")
def get_batch(batch_id: str) -> dict[str, str]:
    """Return a starter order batch record."""

    return {"batch_id": batch_id, "status": "not_found_in_memory"}
