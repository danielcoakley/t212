"""Operator dashboard settings and log routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from isa_system.api.deps import ControlState, get_state
from isa_system.openbb_adapter import OpenBBUpstreamManager
from isa_system.services.ai_model_config import AIModelTask, get_model_config_for_task
from isa_system.settings import get_settings

router = APIRouter(tags=["operator"])


@router.get("/settings")
def settings(state: ControlState = Depends(get_state)) -> dict[str, object]:
    """Return non-secret runtime settings for the dashboard."""

    app_settings = get_settings()
    upstream = OpenBBUpstreamManager().status()
    health_config = get_model_config_for_task(
        AIModelTask.PORTFOLIO_HEALTH_CHECK,
        settings=app_settings,
    )
    valuation_config = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_VALUATION,
        settings=app_settings,
    )
    max_valuation_config = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_VALUATION_MAX,
        settings=app_settings,
    )
    source_config = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_SOURCE_RESEARCH,
        settings=app_settings,
    )
    return {
        "environment": app_settings.environment,
        "mode": state.mode.value,
        "live_armed": state.live_armed,
        "kill_switch_enabled": state.kill_switch_enabled,
        "trading212_environment": app_settings.trading212_environment,
        "openbb_default_provider": app_settings.openbb_default_provider,
        "openbb_locked_revision": upstream.locked_revision,
        "openbb_current_revision": upstream.current_revision,
        "ai_models": {
            "portfolio_health_check": health_config.model_dump(mode="json"),
            "selected_stock_valuation": valuation_config.model_dump(mode="json"),
            "selected_stock_valuation_max": max_valuation_config.model_dump(mode="json"),
            "selected_stock_source_research": source_config.model_dump(mode="json"),
        },
        "deep_valuation_selected_stock_limit": (
            app_settings.openai_deep_research_selected_stock_limit
        ),
        "deep_valuation_max_concurrency": app_settings.openai_deep_valuation_max_concurrency,
    }


@router.get("/logs")
def logs() -> dict[str, object]:
    """Return a lightweight operator log stream placeholder."""

    upstream = OpenBBUpstreamManager().status()
    warnings: list[str] = []
    if upstream.dirty:
        warnings.append("OpenBB vendor checkout has local modifications.")
    if not upstream.matches_lock:
        warnings.append("OpenBB vendor checkout does not match configs/openbb.lock.json.")
    return {"warnings": warnings, "events": []}
