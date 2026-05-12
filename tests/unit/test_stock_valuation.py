"""Tests for selected-stock deep valuation routing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.stock_valuation import run_selected_stock_valuations
from isa_system.services.valuation import HoldingsValuationResponse, HoldingValuation, ValuationMetrics
from isa_system.settings import Settings


def test_selected_stock_valuation_uses_gpt55_high_reasoning(tmp_path: Path) -> None:
    settings = _settings(tmp_path, openai_api_key=SecretStr("test-key"))

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-5.5"
        assert payload["reasoning"] == {"effort": "high"}
        assert payload["max_output_tokens"] == 14000
        assert "tools" not in payload
        return _valuation_response()

    run = run_selected_stock_valuations(
        ["GOOD.L"],
        snapshot=_snapshot(),
        valuation=_valuation(),
        settings=settings,
        transport=httpx.MockTransport(handler),
    )

    assert run.selected_count == 1
    assert run.source_heavy is False
    result = run.results[0]
    assert result.model == "gpt-5.5"
    assert result.reasoning_effort == "high"
    assert result.rating == "Hold"


def test_maximum_depth_uses_xhigh_reasoning(tmp_path: Path) -> None:
    settings = _settings(tmp_path, openai_api_key=SecretStr("test-key"))

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["reasoning"] == {"effort": "xhigh"}
        return _valuation_response()

    run = run_selected_stock_valuations(
        ["GOOD.L"],
        snapshot=_snapshot(),
        valuation=_valuation(),
        settings=settings,
        maximum_depth=True,
        transport=httpx.MockTransport(handler),
    )

    assert run.results[0].reasoning_effort == "xhigh"


def test_source_heavy_mode_runs_o3_pack_before_gpt55(tmp_path: Path) -> None:
    settings = _settings(tmp_path, openai_api_key=SecretStr("test-key"))
    seen_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen_models.append(payload["model"])
        if payload["model"] == "o3-deep-research":
            assert payload["tools"] == [{"type": "web_search_preview"}]
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "summary": "Source pack.",
                            "importantFacts": ["Fact."],
                            "recentDevelopments": [],
                            "risks": [],
                            "sources": [
                                {
                                    "title": "Filing",
                                    "url": "https://example.com/filing",
                                    "publisher": "Example",
                                    "date": "2026-05-01",
                                }
                            ],
                            "missingData": [],
                        }
                    )
                },
            )
        assert payload["model"] == "gpt-5.5"
        assert payload["reasoning"] == {"effort": "high"}
        return _valuation_response()

    run = run_selected_stock_valuations(
        ["GOOD.L"],
        snapshot=_snapshot(),
        valuation=_valuation(),
        settings=settings,
        source_heavy=True,
        transport=httpx.MockTransport(handler),
    )

    assert seen_models == ["o3-deep-research", "gpt-5.5"]
    assert run.source_heavy is True
    assert run.results[0].used_deep_research is True
    assert run.results[0].sources[0].url == "https://example.com/filing"


def test_deep_valuation_requires_selected_tickers(tmp_path: Path) -> None:
    settings = _settings(tmp_path, openai_api_key=SecretStr("test-key"))

    with pytest.raises(ValueError, match="Select at least one stock"):
        run_selected_stock_valuations([], settings=settings)


def test_missing_data_is_surfaced_without_fabrication(tmp_path: Path) -> None:
    settings = _settings(tmp_path, openai_api_key=None)

    run = run_selected_stock_valuations(
        ["MISSING.L"],
        snapshot=_snapshot(positions=[]),
        valuation=HoldingsValuationResponse(
            status="demo",
            environment="demo",
            retrieved_at_utc=datetime(2026, 5, 12, 9, tzinfo=UTC),
            provider="static",
            holdings=[],
            warnings=[],
        ),
        settings=settings,
    )

    result = run.results[0]
    assert result.status == "UNAVAILABLE"
    assert result.rating == "Watch"
    assert any("not found in current broker holdings" in item for item in result.missing_data)
    assert any("OPENAI_API_KEY" in item for item in result.missing_data)


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        operational_db_dsn=f"sqlite:///{tmp_path / 'valuation.sqlite3'}",
        **overrides,
    )


def _snapshot(positions: list[BrokerPosition] | None = None) -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=datetime(2026, 5, 12, 9, tzinfo=UTC),
        account_currency="GBP",
        total_value=1_000.0,
        available_to_trade=200.0,
        positions=positions
        if positions is not None
        else [
            BrokerPosition(
                symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                name="Good Plc",
                isin="GB00GOOD0001",
                currency="GBP",
                quantity=10,
                average_price_paid=90.0,
                current_price=100.0,
                current_value=1_000.0,
            )
        ],
        warnings=[],
    )


def _valuation() -> HoldingsValuationResponse:
    return HoldingsValuationResponse(
        status="demo",
        environment="demo",
        retrieved_at_utc=datetime(2026, 5, 12, 9, tzinfo=UTC),
        provider="static",
        holdings=[
            HoldingValuation(
                symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                research_symbol="GOOD.L",
                name="Good Plc",
                currency="GBP",
                quantity=10,
                current_price=100.0,
                current_value=1_000.0,
                valuation=ValuationMetrics(
                    trailing_pe=18.0,
                    forward_pe=16.0,
                    price_to_book=3.0,
                    dividend_yield=0.02,
                    market_cap=1_000_000_000,
                    beta=1.1,
                ),
                technicals={},
                upcoming_events=[],
                news=[],
                warnings=[],
            )
        ],
        warnings=[],
    )


def _valuation_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "output_text": json.dumps(
                {
                    "ticker": "GOOD.L",
                    "companyName": "Good Plc",
                    "rating": "Hold",
                    "confidence": "medium",
                    "summary": "Balanced valuation.",
                    "businessQuality": {"score": 65, "notes": "Stable quality."},
                    "valuation": {
                        "score": 55,
                        "methodUsed": "relative valuation",
                        "fairValueRange": "95-115",
                        "currentPrice": 100,
                        "marginOfSafety": "limited",
                        "assumptions": ["Provider valuation metrics are current."],
                    },
                    "scenarios": {
                        "bull": {
                            "summary": "Growth improves.",
                            "keyAssumptions": ["Margins expand."],
                            "valuationImplication": "Upside to 125.",
                        },
                        "base": {
                            "summary": "Steady execution.",
                            "keyAssumptions": ["Multiples hold."],
                            "valuationImplication": "Fair value near spot.",
                        },
                        "bear": {
                            "summary": "Growth slows.",
                            "keyAssumptions": ["Margins compress."],
                            "valuationImplication": "Downside to 80.",
                        },
                    },
                    "risks": ["Valuation risk."],
                    "catalysts": ["Next earnings."],
                    "thesisBreakers": ["Balance sheet deterioration."],
                    "portfolioFit": "Already a full-size holding.",
                    "sources": [],
                    "missingData": [],
                    "disclaimer": "Research only, not personal financial advice.",
                }
            ),
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
    )
