"""Config management routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from isa_system.api.schemas import ConfigRequest, ConfigResponse
from isa_system.utils.hashing import sha256_digest

router = APIRouter()
CONFIGS: dict[str, ConfigResponse] = {}


@router.get("/configs")
def list_configs() -> list[ConfigResponse]:
    """List process-local starter configs."""

    return list(CONFIGS.values())


@router.post("/configs", response_model=ConfigResponse)
def create_config(request: ConfigRequest) -> ConfigResponse:
    """Create a config snapshot."""

    config_id = sha256_digest(request.model_dump())[:12]
    response = ConfigResponse(
        config_id=config_id,
        name=request.name,
        version=request.version,
        config_hash=sha256_digest(request.config_text),
    )
    CONFIGS[config_id] = response
    return response


@router.put("/configs/{config_id}", response_model=ConfigResponse)
def update_config(config_id: str, request: ConfigRequest) -> ConfigResponse:
    """Update a config with optimistic versioning."""

    existing = CONFIGS.get(config_id)
    if existing and request.version <= existing.version:
        raise HTTPException(status_code=409, detail="Config version must increase.")
    response = ConfigResponse(
        config_id=config_id,
        name=request.name,
        version=request.version,
        config_hash=sha256_digest(request.config_text),
    )
    CONFIGS[config_id] = response
    return response
