"""FastAPI control plane entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from isa_system.api.routers import (
    audit,
    backtests,
    configs,
    health,
    metrics,
    modes,
<<<<<<< Updated upstream
    operator_report,
=======
    openbb,
    operator,
>>>>>>> Stashed changes
    orders,
    portfolio,
    rebalances,
    recommendations,
    research_reviews,
    signals,
    valuation,
)


def create_app() -> FastAPI:
    """Create the local-only control plane app."""

    app = FastAPI(title="ISA System Control Plane", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:1470",
            "http://localhost:1470",
        ],
        allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):[0-9]+$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(configs.router)
    app.include_router(backtests.router)
    app.include_router(rebalances.router)
    app.include_router(modes.router)
    app.include_router(orders.router)
    app.include_router(audit.router)
    app.include_router(metrics.router)
    app.include_router(openbb.router)
    app.include_router(operator.router)
    app.include_router(portfolio.router)
    app.include_router(recommendations.router)
    app.include_router(operator_report.router)
    app.include_router(research_reviews.router)
    app.include_router(signals.router)
    app.include_router(valuation.router)
    return app


app = create_app()
