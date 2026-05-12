"""Focused helper-level guardrails for the MVP safety workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import SecretStr

from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.db.crud import append_audit_log
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.domain.enums import RuntimeMode
from isa_system.execution.risk_checks import check_kill_switch, check_live_arming
from isa_system.services.deep_research import (
    DeepResearchDecision,
    DeepResearchInput,
    DeepResearchReview,
    DeepResearchStatus,
    run_deep_research,
)
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import HandoffStatus, build_recommendation_handoff
from isa_system.services.recommendation_preview import build_preview_from_recommendation_handoff
from isa_system.services.recommendations import (
    RecommendationsResponse,
    build_recommendations_from_static_data,
)
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics
from isa_system.settings import Settings
from isa_system.utils.time import now_utc


def test_deep_research_missing_key_is_unavailable_without_network() -> None:
    """Missing OpenAI credentials create a blocking fallback review."""

    review = run_deep_research(
        _deep_research_request("GOOD.L"),
        settings=Settings(_env_file=None, openai_api_key=None),
        persist=False,
    )

    assert review.status == DeepResearchStatus.UNAVAILABLE
    assert review.decision is None
    assert review.is_valid_pass is False
    assert "OPENAI_API_KEY" in review.warnings[0]
    assert "cannot approve" in review.thesis


def test_risk_checks_keep_kill_switch_a_hard_live_block() -> None:
    """Kill switch remains an explicit hard block even when live mode is armed."""

    live_check = check_live_arming(RuntimeMode.LIVE, live_armed=True)
    kill_switch_check = check_kill_switch(kill_switch_enabled=True)

    assert live_check.passed is True
    assert kill_switch_check.passed is False
    assert "Kill switch is enabled" in kill_switch_check.message


def test_settings_summary_does_not_render_secret_values() -> None:
    """Settings summaries should never expose local credential contents."""

    settings = Settings(
        _env_file=None,
        trading212_api_key=SecretStr("broker-key"),
        trading212_api_secret=SecretStr("broker-secret"),
        openai_api_key=SecretStr("openai-secret"),
        sec_user_agent="isa-system-test",
    )
    rendered = str(settings.model_dump())

    assert "broker-key" not in rendered
    assert "broker-secret" not in rendered
    assert "openai-secret" not in rendered
    assert "**********" in rendered


def test_sqlite_first_run_creates_parent_and_accepts_audit_rows(tmp_path: Path) -> None:
    """File-backed SQLite starts from an absent artifacts directory."""

    db_path = tmp_path / "artifacts" / "ops" / "isa_system.sqlite3"
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = make_session_factory(engine)

    with factory() as session:
        row = append_audit_log(
            session,
            actor="test.mvp_guardrails",
            action="first_run.sqlite",
            payload={"preview_first": True},
            outcome="ok",
        )
        row_id = row.id
        session.commit()

    assert db_path.exists()
    assert row_id is not None


def test_recommendation_preview_never_sizes_unapproved_or_missing_rows() -> None:
    """Only broker-matched rows with a valid research pass receive preview notional."""

    recommendations = _recommendations_response(["GOOD.L", "WAIT.L"])
    validation = validate_recommendation_instruments(
        recommendations,
        instruments=[_instrument("GOOD.L"), _instrument("WAIT.L")],
    )
    handoff = build_recommendation_handoff(
        recommendations,
        instrument_validation=validation,
        research_reviews={"GOOD.L": _research_review("GOOD.L")},
    )

    preview = build_preview_from_recommendation_handoff(
        selected_symbols=["GOOD.L", "WAIT.L", "MISSING.L"],
        snapshot=_snapshot(total_value=10_000),
        handoff=handoff,
    )
    rows = {row.research_symbol: row for row in preview.rows}

    assert preview.mode == "preview"
    assert preview.selected_count == 3
    assert preview.eligible_count == 1
    assert any("does not submit orders" in warning for warning in preview.warnings)
    assert rows["GOOD.L"].eligible is True
    assert rows["GOOD.L"].estimated_notional_gbp == 400.0
    assert rows["WAIT.L"].eligible is False
    assert rows["WAIT.L"].estimated_notional_gbp == 0.0
    assert "DEEP_RESEARCH_REQUIRED" in rows["WAIT.L"].blockers
    assert rows["MISSING.L"].eligible is False
    assert rows["MISSING.L"].blockers == ["RECOMMENDATION_NOT_FOUND"]


def test_handoff_rows_expose_preview_readiness_without_order_authority() -> None:
    """Even eligible review rows remain context, not submit instructions."""

    recommendations = _recommendations_response(["GOOD.L"])
    validation = validate_recommendation_instruments(
        recommendations,
        instruments=[_instrument("GOOD.L")],
    )
    handoff = build_recommendation_handoff(
        recommendations,
        instrument_validation=validation,
        research_reviews={"GOOD.L": _research_review("GOOD.L")},
    )

    row = handoff.rows[0]
    forbidden_fragments = ("order", "submit", "idempotency", "batch_hash", "authority")

    assert len(handoff.rows) == 1
    assert row.eligible_for_preview is True
    assert row.handoff_status == HandoffStatus.ELIGIBLE
    assert row.research_review_status == "RESEARCH_PASSED"
    assert not any(
        fragment in field.lower() for field in row.model_dump() for fragment in forbidden_fragments
    )


def _snapshot(*, total_value: float | None = None) -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, 9, 0, tzinfo=UTC),
        account_currency="GBP",
        total_value=total_value,
        available_to_trade=total_value,
        positions=[],
        warnings=[],
    )


def _recommendations_response(symbols: list[str]) -> RecommendationsResponse:
    data = {
        symbol: HoldingValuationData(
            symbol=symbol,
            retrieved_at_utc=datetime(2026, 5, 11, 9, 1, tzinfo=UTC),
            daily_adjusted_closes=_rising_closes(260),
            valuation=ValuationMetrics(
                trailing_pe=8.0,
                forward_pe=7.0,
                price_to_book=1.0,
                dividend_yield=0.05,
            ),
        )
        for symbol in symbols
    }
    return build_recommendations_from_static_data(
        _snapshot(),
        data,
        candidates=symbols,
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 11, 9, 2, tzinfo=UTC),
    )


def _rising_closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]


def _instrument(symbol: str) -> Trading212Instrument:
    root = symbol.removesuffix(".L")
    return Trading212Instrument(ticker=f"{root}l_EQ", currencyCode="GBX", type="STOCK")


def _research_review(symbol: str) -> DeepResearchReview:
    generated = now_utc()
    return DeepResearchReview(
        id=f"review-{symbol}",
        symbol=symbol,
        research_symbol=symbol,
        broker_ticker=_instrument(symbol).ticker,
        status=DeepResearchStatus.AVAILABLE,
        decision=DeepResearchDecision.RESEARCH_PASSED,
        thesis="Evidence supports review-only preview sizing.",
        final_score=82,
        model="test-model",
        evidence_hash="hash",
        generated_at_utc=generated,
        expires_at_utc=generated + timedelta(days=7),
        request=_deep_research_request(symbol),
    )


def _deep_research_request(symbol: str) -> DeepResearchInput:
    return DeepResearchInput(
        symbol=symbol,
        research_symbol=symbol,
        broker_ticker=_instrument(symbol).ticker,
        action="REVIEW_BUY",
        source="watchlist",
        component_scores={"composite": 0.5},
        valuation={},
        technicals={},
    )
