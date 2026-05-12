"""Tests for holdings health-check dashboard helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from isa_system.dashboard.pages.health_check import (
    acceptance_requests_from_rows,
    health_report_rows,
)
from isa_system.services.holding_health import (
    HealthPriceTargets,
    HoldingHealthAction,
    HoldingHealthAssessment,
    HoldingHealthReport,
    HoldingHealthReportStatus,
    HoldingHealthUpdate,
)


def test_health_report_rows_overlay_accepted_update() -> None:
    """The editable page rows carry forward accepted targets/actions."""

    report = _report()
    update = HoldingHealthUpdate(
        id="update-1",
        report_id=report.id,
        symbol="GOOD.L",
        updated_at_utc=datetime(2026, 5, 12, 10, tzinfo=UTC),
        accepted_price_targets=HealthPriceTargets(bear=90.0, base=140.0, bull=180.0),
        carried_forward_action=HoldingHealthAction.BUY_MORE,
        adjusted=True,
    )

    rows = health_report_rows(report, [update])

    assert rows[0]["Accept"] is True
    assert rows[0]["Already carried"] == "Yes"
    assert rows[0]["Carried action"] == "BUY_MORE"
    assert rows[0]["Accepted base"] == 140.0


def test_acceptance_requests_only_include_selected_rows() -> None:
    """Only checked rows become persisted carry-forward requests."""

    requests = acceptance_requests_from_rows(
        [
            {
                "Accept": False,
                "Symbol": "SKIP.L",
                "Carried action": "SELL",
                "Accepted bear": 1,
                "Accepted base": 2,
                "Accepted bull": 3,
            },
            {
                "Accept": True,
                "Symbol": "GOOD.L",
                "Carried action": "HOLD",
                "Accepted bear": 90,
                "Accepted base": 120,
                "Accepted bull": 160,
            },
        ]
    )

    assert len(requests) == 1
    symbol, request = requests[0]
    assert symbol == "GOOD.L"
    assert request.carried_forward_action == HoldingHealthAction.HOLD
    assert request.price_targets is not None
    assert request.price_targets.base == 120.0


def _report() -> HoldingHealthReport:
    generated = datetime(2026, 5, 12, 9, tzinfo=UTC)
    return HoldingHealthReport(
        id="holding-health-test",
        status=HoldingHealthReportStatus.AVAILABLE,
        model="test-model",
        generated_at_utc=generated,
        holdings_snapshot_at_utc=generated,
        holding_count=1,
        evidence_hash="hash",
        summary="Health report.",
        assessments=[
            HoldingHealthAssessment(
                symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                research_symbol="GOOD.L",
                company_name="Good Plc",
                current_price=100.0,
                current_value=1_000.0,
                current_weight_pct=10.0,
                recommended_action=HoldingHealthAction.HOLD,
                action_rationale="Keep holding.",
                price_targets=HealthPriceTargets(bear=80.0, base=120.0, bull=160.0),
                bear_case="Bear.",
                base_case="Base.",
                bull_case="Bull.",
                confidence_score=70,
            )
        ],
    )
