"""Release-readiness checks for newly integrated MVP API routes."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from isa_system.api.deps import STATE
from isa_system.api.main import app
from isa_system.domain.enums import RuntimeMode
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import RecommendationHandoffResponse
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    RecommendationPreviewRow,
)
from isa_system.services.recommendations import RecommendationsResponse
from isa_system.settings import Settings


@pytest.fixture(autouse=True)
def reset_control_state() -> Iterator[None]:
    """Keep process-local mode state deterministic for release-readiness tests."""

    STATE.mode = RuntimeMode.PREVIEW
    STATE.live_armed = False
    STATE.kill_switch_enabled = False
    yield
    STATE.mode = RuntimeMode.PREVIEW
    STATE.live_armed = False
    STATE.kill_switch_enabled = False


def test_release_routes_are_discoverable_in_openapi() -> None:
    """The release-critical report and paper-cycle endpoints stay publicly visible."""

    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]

    assert paths["/operator-report"]["post"]["tags"] == ["operator-report"]
    assert _response_ref(paths["/operator-report"]["post"]) == "OperatorReportSummary"

    paper_cycle_post = paths["/rebalances/from-recommendations/paper-cycle"]["post"]
    assert _request_ref(paper_cycle_post) == "RecommendationsPreviewRequest"
    assert _response_ref(paper_cycle_post) == "PersistedPaperCycle"

    paper_cycle_get = paths["/rebalances/paper-cycles/{cycle_id}"]["get"]
    assert _response_ref(paper_cycle_get) == "PersistedPaperCycle"
    assert paper_cycle_get["parameters"][0]["name"] == "cycle_id"


def test_paper_cycle_reload_returns_404_for_unknown_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reload endpoint reports missing paper evidence without network or broker calls."""

    settings = Settings(_env_file=None, operational_db_dsn=f"sqlite:///{tmp_path / 'ops.db'}")
    monkeypatch.setattr("isa_system.services.paper_persistence.get_settings", lambda: settings)

    response = TestClient(app).get("/rebalances/paper-cycles/paper-cycle-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Paper cycle not found."


def test_report_and_paper_cycle_routes_leave_live_submit_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Report generation and paper persistence must not arm or authorize live submit."""

    settings = Settings(_env_file=None, operational_db_dsn=f"sqlite:///{tmp_path / 'ops.db'}")
    monkeypatch.setattr("isa_system.services.paper_persistence.get_settings", lambda: settings)
    _patch_report_dependencies(monkeypatch)
    _patch_recommendation_preview_dependencies(monkeypatch)

    client = TestClient(app)
    report_response = client.post("/operator-report", json={})
    paper_cycle_response = client.post(
        "/rebalances/from-recommendations/paper-cycle",
        json={"symbols": ["GOOD.L"], "total_equity_gbp": 10_000},
    )

    assert report_response.status_code == 200
    assert paper_cycle_response.status_code == 200
    assert report_response.json()["report_kind"] == "operator_report_shell"
    assert paper_cycle_response.json()["persistence_status"] == "persisted"
    assert STATE.mode == RuntimeMode.PREVIEW
    assert STATE.live_armed is False

    submit_response = client.post(
        "/rebalances/submit",
        json={"batch_hash": paper_cycle_response.json()["id"], "mode": "live"},
    )

    assert submit_response.status_code == 403
    assert submit_response.json()["detail"] == "Live trading is not armed."


def _patch_report_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    generated_at = datetime(2026, 5, 11, 12, tzinfo=UTC)
    snapshot = BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=generated_at,
        account_currency="GBP",
        total_value=10_000.0,
        available_to_trade=1_000.0,
        positions=[],
        warnings=[],
    )
    recommendations = RecommendationsResponse(
        status="demo",
        environment="demo",
        retrieved_at_utc=generated_at,
        provider="release-readiness-fixture",
        recommendations=[],
        warnings=[],
    )
    handoff = RecommendationHandoffResponse(
        generated_at_utc=generated_at,
        provider="release-readiness-fixture",
        rows=[],
        eligible_count=0,
        review_required_count=0,
        blocked_count=0,
        warnings=["Hand-off is review-only and never submits orders."],
    )

    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.get_settings",
        lambda: Settings(_env_file=None),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.load_trading212_portfolio",
        lambda: snapshot,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.load_broker_market_scan_universe",
        lambda: SimpleNamespace(symbols=[], warnings=[]),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.build_recommendations",
        lambda *args, **kwargs: recommendations,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.validate_recommendation_instruments",
        lambda response: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.latest_deep_research_reviews",
        lambda symbols: {},
    )
    monkeypatch.setattr(
        "isa_system.api.routers.operator_report.build_recommendation_handoff",
        lambda recommendations, instrument_validation, research_reviews: handoff,
    )


def _patch_recommendation_preview_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_preview(
        selected_symbols: list[str],
        snapshot: object,
        handoff: object,
        total_equity_gbp: object,
    ) -> RecommendationPreviewResponse:
        return RecommendationPreviewResponse(
            generated_at_utc=datetime(2026, 5, 11, 12, tzinfo=UTC),
            total_equity_gbp=10_000.0,
            selected_count=1,
            eligible_count=1,
            estimated_total_cost_gbp=12.5,
            rows=[
                RecommendationPreviewRow(
                    symbol=selected_symbols[0],
                    research_symbol=selected_symbols[0],
                    broker_ticker="GOODl_EQ",
                    side="BUY",
                    eligible=True,
                    target_weight=0.04,
                    estimated_notional_gbp=400.0,
                    estimated_total_cost_gbp=12.5,
                    research_review_status="RESEARCH_PASSED",
                    rationale="Preview-only sizing.",
                )
            ],
        )

    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio",
        lambda: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_broker_market_scan_universe",
        lambda: SimpleNamespace(symbols=["GOOD.L"]),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendations",
        lambda *args, **kwargs: SimpleNamespace(
            recommendations=[SimpleNamespace(candidate=SimpleNamespace(research_symbol="GOOD.L"))]
        ),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.validate_recommendation_instruments",
        lambda recommendations: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.latest_deep_research_reviews",
        lambda symbols: {},
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_recommendation_handoff",
        lambda recommendations, instrument_validation, research_reviews: object(),
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.build_preview_from_recommendation_handoff",
        fake_preview,
    )


def _response_ref(operation: dict[str, object]) -> str:
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    return str(ref).rsplit("/", maxsplit=1)[-1]


def _request_ref(operation: dict[str, object]) -> str:
    ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    return str(ref).rsplit("/", maxsplit=1)[-1]
