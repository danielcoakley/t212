"""Central OpenAI model routing for research and portfolio tasks."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from isa_system.settings import Settings, get_settings


class AIModelTask(StrEnum):
    """Supported AI task routes."""

    PORTFOLIO_HEALTH_CHECK = "portfolio_health_check"
    PORTFOLIO_HEALTH_CHECK_DETAILED = "portfolio_health_check_detailed"
    SELECTED_STOCK_VALUATION = "selected_stock_valuation"
    SELECTED_STOCK_VALUATION_MAX = "selected_stock_valuation_max"
    SELECTED_STOCK_SOURCE_RESEARCH = "selected_stock_source_research"


class AIModelConfig(BaseModel):
    """Resolved model configuration for one AI task."""

    task: AIModelTask
    model: str
    reasoning_effort: str | None = None
    max_output_tokens: int
    use_web_search: bool = False
    uses_deep_research: bool = False
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)


def get_model_config_for_task(
    task: AIModelTask | str,
    *,
    settings: Settings | None = None,
    explicit_source_research: bool = False,
) -> AIModelConfig:
    """Return the configured model route for a supported AI task."""

    app_settings = settings or get_settings()
    resolved_task = AIModelTask(task)
    if resolved_task == AIModelTask.PORTFOLIO_HEALTH_CHECK:
        return AIModelConfig(
            task=resolved_task,
            model=app_settings.openai_health_check_model,
            reasoning_effort=app_settings.openai_health_check_reasoning_effort,
            max_output_tokens=app_settings.openai_health_check_max_output_tokens,
        )
    if resolved_task == AIModelTask.PORTFOLIO_HEALTH_CHECK_DETAILED:
        return AIModelConfig(
            task=resolved_task,
            model=app_settings.openai_health_check_model,
            reasoning_effort=app_settings.openai_health_check_detailed_reasoning_effort,
            max_output_tokens=app_settings.openai_health_check_max_output_tokens,
        )
    if resolved_task == AIModelTask.SELECTED_STOCK_VALUATION:
        return AIModelConfig(
            task=resolved_task,
            model=app_settings.openai_stock_valuation_model,
            reasoning_effort=app_settings.openai_stock_valuation_reasoning_effort,
            max_output_tokens=app_settings.openai_stock_valuation_max_output_tokens,
        )
    if resolved_task == AIModelTask.SELECTED_STOCK_VALUATION_MAX:
        return AIModelConfig(
            task=resolved_task,
            model=app_settings.openai_stock_valuation_model,
            reasoning_effort=app_settings.openai_stock_valuation_max_reasoning_effort,
            max_output_tokens=app_settings.openai_stock_valuation_max_output_tokens,
        )

    enabled = app_settings.openai_enable_o3_source_research or explicit_source_research
    notes = (
        []
        if enabled
        else [
            "o3 source-heavy research is disabled. Set "
            "OPENAI_ENABLE_O3_SOURCE_RESEARCH=true or request source-heavy mode explicitly."
        ]
    )
    return AIModelConfig(
        task=resolved_task,
        model=app_settings.openai_source_research_model,
        reasoning_effort=None,
        max_output_tokens=app_settings.openai_source_research_max_output_tokens,
        use_web_search=enabled,
        uses_deep_research=enabled,
        enabled=enabled,
        notes=notes,
    )


def getModelConfigForTask(
    task: AIModelTask | str,
    options: dict[str, Any] | None = None,
    *,
    settings: Settings | None = None,
) -> AIModelConfig:
    """Camel-case compatibility wrapper for callers expecting JS-style naming."""

    options = options or {}
    return get_model_config_for_task(
        task,
        settings=settings,
        explicit_source_research=bool(options.get("source_heavy") or options.get("sourceHeavy")),
    )
