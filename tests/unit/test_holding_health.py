"""Tests for current-holdings health reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from pydantic import SecretStr

from isa_system.services.holding_health import (
    HealthPriceTargets,
    HoldingHealthAction,
    HoldingHealthReportStatus,
    HoldingHealthUpdateRequest,
    accept_holding_health_update,
    latest_holding_health_report_detail,
    latest_holding_health_updates,
    run_holding_health_report,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import (
    DailyAdjustedClose,
    HoldingValuationData,
    StaticValuationProvider,
    ValuationMetrics,
    value_current_holdings,
)
from isa_system.settings import Settings


def test_holding_health_report_falls_back_without_openai_key(tmp_path: Path) -> None:
    """Offline/no-key runs still create conservative persisted report history."""

    settings = _settings(tmp_path)
    snapshot = _snapshot()
    valuation = _valuation(snapshot)

    report = run_holding_health_report(snapshot, valuation, settings=settings)
    latest = latest_holding_health_report_detail(settings=settings)

    assert report.status == HoldingHealthReportStatus.DETERMINISTIC_FALLBACK
    assert report.holding_count == 1
    assert report.assessments[0].symbol == "GOOD_US_EQ"
    assert report.assessments[0].recommended_action == HoldingHealthAction.HOLD
    assert report.assessments[0].price_targets.base == 54.0
    assert latest is not None
    assert latest.report.id == report.id
    assert any("OPENAI_API_KEY" in warning for warning in report.warnings)


def test_holding_health_report_uses_configured_openai_model(tmp_path: Path) -> None:
    """OpenAI-backed runs use the health model and parse report JSON."""

    settings = _settings(
        tmp_path,
        openai_api_key=SecretStr("test-key"),
        openai_health_check_model="test-health-model",
        openai_health_check_reasoning_effort="medium",
        openai_health_check_max_output_tokens=1234,
    )
    snapshot = _snapshot()
    valuation = _valuation(snapshot)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "test-health-model"
        assert payload["reasoning"] == {"effort": "medium"}
        assert payload["max_output_tokens"] == 1234
        assert "tools" not in payload
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "portfolioHealthScore": 77,
                        "summary": "Good Inc remains attractive but needs review.",
                        "keyFindings": ["Position size is modest."],
                        "riskScores": {
                            "concentration": 20,
                            "valuation": 35,
                            "balanceSheet": 30,
                            "earningsQuality": 25,
                            "dividend": 15,
                            "macro": 40,
                        },
                        "holdingsToReview": [
                            {
                                "ticker": "GOOD_US_EQ",
                                "companyName": "Good Inc",
                                "reason": "Review valuation after latest data.",
                                "riskLevel": "medium",
                                "suggestedAction": "Hold",
                                "confidence": "medium",
                            }
                        ],
                        "portfolioActions": ["Keep monitoring valuation."],
                        "missingData": [],
                        "disclaimer": "Research only, not advice.",
                        "portfolio_level_notes": ["Position size is modest."],
                        "warnings": ["Verify sources before action."],
                        "assessments": [
                            {
                                "symbol": "GOOD_US_EQ",
                                "recommended_action": "BUY_MORE",
                                "action_rationale": "Upside case improved.",
                                "bear_case_price_target": 42.0,
                                "base_case_price_target": 62.0,
                                "bull_case_price_target": 81.0,
                                "bear_case": "Margins compress.",
                                "base_case": "Growth continues.",
                                "bull_case": "Multiple expands.",
                                "key_risks": ["Execution risk."],
                                "evidence_gaps": ["Check latest filing."],
                                "confidence_score": 74,
                            }
                        ],
                    }
                )
            },
        )

    report = run_holding_health_report(
        snapshot,
        valuation,
        settings=settings,
        transport=httpx.MockTransport(handler),
    )

    assert report.status == HoldingHealthReportStatus.AVAILABLE
    assert report.model == "test-health-model"
    assert report.reasoning_effort == "medium"
    assert report.used_deep_research is False
    assert report.portfolio_health_score == 77
    assert report.risk_scores.valuation == 35
    assert report.holdings_to_review[0].suggested_action == "Hold"
    assessment = report.assessments[0]
    assert assessment.recommended_action == HoldingHealthAction.BUY_MORE
    assert assessment.price_targets.bear == 42.0
    assert assessment.price_targets.base == 62.0
    assert assessment.price_targets.bull == 81.0
    assert assessment.confidence_score == 74


def test_detailed_holding_health_uses_high_reasoning(tmp_path: Path) -> None:
    """Detailed health checks keep the health model but increase reasoning effort."""

    settings = _settings(tmp_path, openai_api_key=SecretStr("test-key"))
    snapshot = _snapshot()
    valuation = _valuation(snapshot)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-5.5"
        assert payload["reasoning"] == {"effort": "high"}
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "portfolioHealthScore": 70,
                        "summary": "Detailed review complete.",
                        "keyFindings": [],
                        "riskScores": {},
                        "holdingsToReview": [],
                        "portfolioActions": [],
                        "missingData": [],
                        "disclaimer": "Research only.",
                        "warnings": [],
                        "assessments": [],
                    }
                )
            },
        )

    report = run_holding_health_report(
        snapshot,
        valuation,
        settings=settings,
        transport=httpx.MockTransport(handler),
        detailed=True,
    )

    assert report.reasoning_effort == "high"


def test_accepting_adjusted_health_targets_is_persisted(tmp_path: Path) -> None:
    """Operator-adjusted targets/actions are stored separately from report history."""

    settings = _settings(tmp_path)
    report = run_holding_health_report(_snapshot(), _valuation(_snapshot()), settings=settings)

    update = accept_holding_health_update(
        report.id,
        "GOOD_US_EQ",
        HoldingHealthUpdateRequest(
            price_targets=HealthPriceTargets(bear=40.0, base=65.0, bull=90.0),
            carried_forward_action=HoldingHealthAction.HOLD,
            notes="Manual target adjustment after review.",
        ),
        settings=settings,
    )
    latest_updates = latest_holding_health_updates(["GOOD_US_EQ"], settings=settings)
    latest = latest_holding_health_report_detail(settings=settings)

    assert update.adjusted is True
    assert update.accepted_price_targets.base == 65.0
    assert update.carried_forward_action == HoldingHealthAction.HOLD
    assert latest_updates["GOOD_US_EQ"].id == update.id
    assert latest is not None
    assert latest.updates[0].id == update.id


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        operational_db_dsn=f"sqlite:///{tmp_path / 'health.sqlite3'}",
        **overrides,
    )


def _snapshot() -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=datetime(2026, 5, 12, 9, tzinfo=UTC),
        account_currency="GBP",
        total_value=1_000.0,
        available_to_trade=200.0,
        positions=[
            BrokerPosition(
                symbol="GOOD_US_EQ",
                broker_ticker="GOOD_US_EQ",
                name="Good Inc",
                isin="US000GOOD001",
                currency="USD",
                quantity=10,
                average_price_paid=40.0,
                current_price=50.0,
                current_value=500.0,
            )
        ],
        warnings=[],
    )


def _valuation(snapshot: BrokerPortfolioSnapshot):
    generated = datetime(2026, 5, 12, 9, tzinfo=UTC)
    provider = StaticValuationProvider(
        {
            "GOOD": HoldingValuationData(
                symbol="GOOD",
                retrieved_at_utc=generated,
                daily_adjusted_closes=[
                    DailyAdjustedClose(
                        ts_utc=generated - timedelta(days=260 - index),
                        adj_close=float(index + 1),
                    )
                    for index in range(260)
                ],
                valuation=ValuationMetrics(
                    trailing_pe=20.0,
                    forward_pe=18.0,
                    price_to_book=4.0,
                    dividend_yield=0.01,
                    market_cap=10_000_000_000,
                ),
            )
        }
    )
    return value_current_holdings(snapshot, provider=provider)
