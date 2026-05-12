"""FastAPI control plane entry point."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from isa_system.api.routers import (
    audit,
    backtests,
    broker,
    candidates,
    configs,
    discovery,
    enrichment,
    health,
    holding_health,
    metrics,
    modes,
    operator_report,
    orchestrator,
    orders,
    portfolio,
    portfolio_manager,
    rebalances,
    recommendations,
    research_reports,
    research_reviews,
    scores,
    thesis,
    valuation,
    web_app,
    workspace,
)
from isa_system.settings import get_settings


def create_app() -> FastAPI:
    """Create the local-only control plane app."""

    app = FastAPI(title="ISA System Control Plane", version="0.1.0")
    app.include_router(health.router)
    app.include_router(holding_health.router)
    app.include_router(broker.router)
    app.include_router(discovery.router)
    app.include_router(candidates.router)
    app.include_router(enrichment.router)
    app.include_router(scores.router)
    app.include_router(thesis.router)
    app.include_router(research_reports.router)
    app.include_router(workspace.router)
    app.include_router(orchestrator.router)
    app.include_router(configs.router)
    app.include_router(backtests.router)
    app.include_router(rebalances.router)
    app.include_router(modes.router)
    app.include_router(orders.router)
    app.include_router(audit.router)
    app.include_router(metrics.router)
    app.include_router(portfolio.router)
    app.include_router(portfolio_manager.router)
    app.include_router(recommendations.router)
    app.include_router(operator_report.router)
    app.include_router(research_reviews.router)
    app.include_router(valuation.router)
    app.include_router(web_app.router)
    app.mount(
        "/dashboard-assets",
        StaticFiles(directory=web_app.assets_dir()),
        name="dashboard-assets",
    )
    return app


app = create_app()


def main() -> None:
    """Run the local control plane on the configured portfolio API port."""

    settings = get_settings()
    uvicorn.run("isa_system.api.main:app", host=settings.bind_host, port=settings.bind_port)


if __name__ == "__main__":
    main()
