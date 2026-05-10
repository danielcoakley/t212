"""FastAPI control plane entry point."""

from __future__ import annotations

from fastapi import FastAPI

from isa_system.api.routers import (
    audit,
    backtests,
    configs,
    health,
    metrics,
    modes,
    orders,
    portfolio,
    rebalances,
    valuation,
)


def create_app() -> FastAPI:
    """Create the local-only control plane app."""

    app = FastAPI(title="ISA System Control Plane", version="0.1.0")
    app.include_router(health.router)
    app.include_router(configs.router)
    app.include_router(backtests.router)
    app.include_router(rebalances.router)
    app.include_router(modes.router)
    app.include_router(orders.router)
    app.include_router(audit.router)
    app.include_router(metrics.router)
    app.include_router(portfolio.router)
    app.include_router(valuation.router)
    return app


app = create_app()
