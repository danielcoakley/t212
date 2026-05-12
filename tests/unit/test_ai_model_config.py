"""Tests for central OpenAI model routing."""

from __future__ import annotations

from isa_system.services.ai_model_config import AIModelTask, get_model_config_for_task
from isa_system.settings import Settings


def test_default_model_routing_keeps_o3_out_of_health_checks() -> None:
    settings = Settings(_env_file=None)

    health = get_model_config_for_task(AIModelTask.PORTFOLIO_HEALTH_CHECK, settings=settings)
    detailed = get_model_config_for_task(
        AIModelTask.PORTFOLIO_HEALTH_CHECK_DETAILED,
        settings=settings,
    )
    valuation = get_model_config_for_task(AIModelTask.SELECTED_STOCK_VALUATION, settings=settings)
    max_depth = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_VALUATION_MAX,
        settings=settings,
    )
    source = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_SOURCE_RESEARCH,
        settings=settings,
    )

    assert health.model == "gpt-5.5"
    assert health.reasoning_effort == "medium"
    assert health.uses_deep_research is False
    assert detailed.reasoning_effort == "high"
    assert valuation.model == "gpt-5.5"
    assert valuation.reasoning_effort == "high"
    assert max_depth.reasoning_effort == "xhigh"
    assert source.model == "o3-deep-research"
    assert source.enabled is False
    assert source.uses_deep_research is False


def test_environment_style_overrides_are_respected() -> None:
    settings = Settings(
        _env_file=None,
        openai_health_check_model="health-model",
        openai_stock_valuation_model="gpt-5.5-pro",
        openai_enable_o3_source_research=True,
    )

    health = get_model_config_for_task(AIModelTask.PORTFOLIO_HEALTH_CHECK, settings=settings)
    valuation = get_model_config_for_task(AIModelTask.SELECTED_STOCK_VALUATION, settings=settings)
    source = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_SOURCE_RESEARCH,
        settings=settings,
    )

    assert health.model == "health-model"
    assert valuation.model == "gpt-5.5-pro"
    assert source.enabled is True
    assert source.uses_deep_research is True


def test_explicit_source_heavy_enables_o3_for_selected_stocks_only() -> None:
    settings = Settings(_env_file=None, openai_enable_o3_source_research=False)

    source = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_SOURCE_RESEARCH,
        settings=settings,
        explicit_source_research=True,
    )

    assert source.enabled is True
    assert source.model == "o3-deep-research"
    assert source.use_web_search is True
