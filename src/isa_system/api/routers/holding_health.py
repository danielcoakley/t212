"""Current-holdings health report routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from isa_system.services.holding_health import (
    HoldingHealthReport,
    HoldingHealthReportDetail,
    HoldingHealthUpdate,
    HoldingHealthUpdateRequest,
    accept_holding_health_update,
    get_holding_health_report_detail,
    latest_holding_health_report_detail,
    list_holding_health_reports,
    run_holding_health_report,
)
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.valuation import value_current_holdings
from isa_system.settings import get_settings

router = APIRouter(prefix="/health-check", tags=["holding-health"])


class RunHealthCheckRequest(BaseModel):
    """Options for an on-demand portfolio health check."""

    model_config = ConfigDict(extra="forbid")

    detailed: bool = False


@router.post("/run", response_model=HoldingHealthReportDetail)
def run_health_check(request: RunHealthCheckRequest | None = None) -> HoldingHealthReportDetail:
    """Run a current-holdings health report and persist the run history."""

    settings = get_settings()
    snapshot = load_trading212_portfolio(force_refresh=True)
    valuation = value_current_holdings(snapshot)
    report = run_holding_health_report(
        snapshot,
        valuation,
        settings=settings,
        detailed=(request.detailed if request is not None else False),
    )
    detail = get_holding_health_report_detail(report.id, settings=settings)
    if detail is None:
        return HoldingHealthReportDetail(report=report, updates=[])
    return detail


@router.get("/latest", response_model=HoldingHealthReportDetail)
def latest_health_check() -> HoldingHealthReportDetail:
    """Return the latest current-holdings health report."""

    detail = latest_holding_health_report_detail(settings=get_settings())
    if detail is None:
        raise HTTPException(status_code=404, detail="No holdings health report exists yet.")
    return detail


@router.get("/reports", response_model=list[HoldingHealthReport])
def health_check_reports(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[HoldingHealthReport]:
    """Return recent health report history."""

    return list_holding_health_reports(settings=get_settings(), limit=limit)


@router.get("/reports/{report_id}", response_model=HoldingHealthReportDetail)
def health_check_report(report_id: str) -> HoldingHealthReportDetail:
    """Return one health report and its operator updates."""

    detail = get_holding_health_report_detail(report_id, settings=get_settings())
    if detail is None:
        raise HTTPException(status_code=404, detail="No holdings health report exists for ID.")
    return detail


@router.post(
    "/reports/{report_id}/holdings/{symbol}/accept",
    response_model=HoldingHealthUpdate,
)
def accept_health_check_update(
    report_id: str, symbol: str, request: HoldingHealthUpdateRequest
) -> HoldingHealthUpdate:
    """Accept or adjust a holding's report targets and action for carry-forward."""

    try:
        return accept_holding_health_update(report_id, symbol, request, settings=get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
