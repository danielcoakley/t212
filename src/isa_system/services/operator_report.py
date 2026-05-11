"""Side-effect-free operator report shell for MVP pilot evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, Field, SecretStr

from isa_system.domain.enums import RuntimeMode
from isa_system.services.deep_research import DeepResearchReview
from isa_system.services.pilot_workflow import PilotPaperWorkflowSummary
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import RecommendationHandoffResponse
from isa_system.services.recommendation_preview import RecommendationPreviewResponse
from isa_system.services.recommendations import RecommendationsResponse
from isa_system.settings import Settings
from isa_system.utils.time import now_utc, require_utc

STALE_AFTER = timedelta(hours=24)

ReportSectionKey = Literal[
    "account",
    "recommendations",
    "research",
    "preview",
    "pilot_paper",
    "management",
]
ReportStatus = Literal[
    "available",
    "partial",
    "missing",
    "stale",
    "unavailable",
    "blocked",
    "needs_attention",
]
ReportValue = str | int | float | bool | None


class OperatorReportItem(BaseModel):
    """One compact fact in a report section."""

    label: str
    value: ReportValue = None
    status: ReportStatus | Literal["info"] = "info"
    detail: str | None = None


class OperatorReportSection(BaseModel):
    """Markdown-ready evidence section for the report shell."""

    key: ReportSectionKey
    title: str
    status: ReportStatus
    summary: str
    source_generated_at_utc: datetime | None = None
    items: list[OperatorReportItem] = Field(default_factory=list)
    records: list[dict[str, ReportValue]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OperatorManagementStatus(BaseModel):
    """Safe management status for the report without exposing secrets."""

    runtime_mode: str
    live_armed: bool
    kill_switch_enabled: bool
    broker_credentials_configured: bool
    deep_research_configured: bool
    optional_provider_count: int = 0
    summary: str | None = None


class OperatorReportSummary(BaseModel):
    """Aggregate report shell for JSON and Markdown export surfaces."""

    report_kind: Literal["operator_report_shell"] = "operator_report_shell"
    generated_at_utc: datetime
    status: ReportStatus
    sections: list[OperatorReportSection]
    warnings: list[str] = Field(default_factory=list)
    markdown: str


class _ControlStateLike(Protocol):
    """Runtime state shape shared by API deps and tests."""

    mode: RuntimeMode | str
    live_armed: bool
    kill_switch_enabled: bool


def build_management_report_status(
    settings: Settings,
    *,
    state: _ControlStateLike | None = None,
) -> OperatorManagementStatus:
    """Build a secret-free management snapshot for the report shell."""

    mode = getattr(state, "mode", settings.runtime_mode)
    return OperatorManagementStatus(
        runtime_mode=_mode_value(mode),
        live_armed=bool(getattr(state, "live_armed", settings.live_armed)),
        kill_switch_enabled=bool(
            getattr(state, "kill_switch_enabled", settings.kill_switch_enabled)
        ),
        broker_credentials_configured=_has_secret(settings.trading212_api_key)
        and _has_secret(settings.trading212_api_secret),
        deep_research_configured=_has_secret(settings.openai_api_key),
        optional_provider_count=_optional_provider_count(settings),
    )


def build_operator_report(
    *,
    account_snapshot: BrokerPortfolioSnapshot | None = None,
    recommendations: RecommendationsResponse | None = None,
    handoff: RecommendationHandoffResponse | None = None,
    research_reviews: Mapping[str, DeepResearchReview] | None = None,
    preview: RecommendationPreviewResponse | None = None,
    pilot_workflow: PilotPaperWorkflowSummary | None = None,
    management: OperatorManagementStatus | None = None,
    as_of_utc: datetime | None = None,
) -> OperatorReportSummary:
    """Aggregate available MVP evidence into a conservative report shell."""

    as_of = require_utc(as_of_utc or now_utc())
    sections = [
        _account_section(account_snapshot, as_of),
        _recommendations_section(recommendations, handoff, as_of),
        _research_section(research_reviews, handoff, as_of),
        _preview_section(preview, as_of),
        _pilot_paper_section(pilot_workflow, as_of),
        _management_section(management),
    ]
    status = _overall_status(sections)
    warnings = _report_warnings(sections)
    markdown = _markdown_report(as_of, status, sections, warnings)
    return OperatorReportSummary(
        generated_at_utc=as_of,
        status=status,
        sections=sections,
        warnings=warnings,
        markdown=markdown,
    )


def _account_section(
    snapshot: BrokerPortfolioSnapshot | None,
    as_of: datetime,
) -> OperatorReportSection:
    if snapshot is None:
        return _missing_section(
            "account",
            "Account",
            "No broker account snapshot was supplied.",
            ["account_snapshot"],
        )

    retrieved_at = require_utc(snapshot.retrieved_at_utc)
    if snapshot.status == "not_configured":
        status: ReportStatus = "missing"
        summary = "Trading 212 read-only account context is not configured."
    elif snapshot.status == "error":
        status = "unavailable"
        summary = "Trading 212 read-only account context could not be loaded."
    else:
        status = _freshness_status(retrieved_at, as_of)
        summary = (
            f"{snapshot.status} account context with {len(snapshot.positions)} position(s) "
            f"retrieved from the broker."
        )

    missing = []
    if snapshot.total_value is None:
        missing.append("total_value")
    if snapshot.available_to_trade is None:
        missing.append("available_to_trade")
    return OperatorReportSection(
        key="account",
        title="Account",
        status=status,
        summary=summary,
        source_generated_at_utc=retrieved_at,
        items=[
            _item("Broker status", snapshot.status, status),
            _item("Broker environment", snapshot.environment),
            _item(
                "Account currency",
                snapshot.account_currency,
                _value_status(snapshot.account_currency),
            ),
            _item("Total value GBP", snapshot.total_value, _value_status(snapshot.total_value)),
            _item(
                "Available to trade GBP",
                snapshot.available_to_trade,
                _value_status(snapshot.available_to_trade),
            ),
            _item("Reserved for orders GBP", snapshot.reserved_for_orders),
            _item("Position count", len(snapshot.positions)),
            _item("Warning count", len(snapshot.warnings)),
        ],
        records=[
            {
                "symbol": position.symbol,
                "broker_ticker": position.broker_ticker,
                "name": position.name,
                "isin": position.isin,
                "currency": position.currency,
                "quantity": position.quantity,
                "current_value": position.current_value,
            }
            for position in snapshot.positions
        ],
        missing_data=missing,
        warnings=_stale_warning(retrieved_at, as_of, "Broker account snapshot")
        + list(snapshot.warnings),
    )


def _recommendations_section(
    recommendations: RecommendationsResponse | None,
    handoff: RecommendationHandoffResponse | None,
    as_of: datetime,
) -> OperatorReportSection:
    if recommendations is None:
        return _missing_section(
            "recommendations",
            "Recommendations",
            "No recommendation snapshot was supplied.",
            ["recommendations"],
        )

    generated_at = require_utc(recommendations.retrieved_at_utc)
    status = _freshness_status(generated_at, as_of)
    missing = [] if handoff is not None else ["recommendation_handoff"]
    if handoff is None and status == "available":
        status = "partial"
    if not recommendations.recommendations:
        status = "partial"

    action_counts: dict[str, int] = {}
    for row in recommendations.recommendations:
        action_counts[row.action.value] = action_counts.get(row.action.value, 0) + 1

    handoff_items: list[OperatorReportItem] = []
    handoff_records: list[dict[str, ReportValue]] = []
    handoff_warnings: list[str] = []
    if handoff is not None:
        handoff_items = [
            _item("Preview eligible rows", handoff.eligible_count),
            _item("Review required rows", handoff.review_required_count),
            _item("Blocked rows", handoff.blocked_count),
        ]
        handoff_records = [
            {
                "symbol": row.symbol,
                "research_symbol": row.research_symbol,
                "action": row.recommendation_action.value,
                "handoff_status": row.handoff_status.value,
                "preview_action": row.proposed_preview_action,
                "eligible_for_preview": row.eligible_for_preview,
                "research_status": row.research_review_status,
                "blockers": _join(row.blockers),
            }
            for row in handoff.rows
        ]
        handoff_warnings = list(handoff.warnings)

    return OperatorReportSection(
        key="recommendations",
        title="Recommendations",
        status=status,
        summary=(
            f"{len(recommendations.recommendations)} review-only recommendation row(s) "
            f"from {recommendations.provider}."
        ),
        source_generated_at_utc=generated_at,
        items=[
            _item("Provider", recommendations.provider),
            _item("Recommendation rows", len(recommendations.recommendations)),
            _item("Action counts", _counts_text(action_counts)),
            _item("Warning count", len(recommendations.warnings) + len(handoff_warnings)),
            *handoff_items,
        ],
        records=handoff_records or _recommendation_records(recommendations),
        missing_data=missing,
        warnings=_stale_warning(generated_at, as_of, "Recommendation snapshot")
        + list(recommendations.warnings)
        + handoff_warnings,
    )


def _research_section(
    research_reviews: Mapping[str, DeepResearchReview] | None,
    handoff: RecommendationHandoffResponse | None,
    as_of: datetime,
) -> OperatorReportSection:
    if research_reviews is None and handoff is None:
        return _missing_section(
            "research",
            "Research",
            "No deep research review map or hand-off status was supplied.",
            ["research_reviews", "recommendation_handoff"],
        )

    reviews = list((research_reviews or {}).values())
    unique_reviews = list({review.id: review for review in reviews}.values())
    required_rows = [row for row in (handoff.rows if handoff else []) if row.deep_research_required]
    missing_required = [
        row.research_symbol
        for row in required_rows
        if (row.research_review_status or "MISSING") == "MISSING"
    ]
    status_counts: dict[str, int] = {}
    valid_pass_count = 0
    expired_count = 0
    latest_at: datetime | None = None
    for review in unique_reviews:
        status_counts[review.status.value] = status_counts.get(review.status.value, 0) + 1
        if _review_is_valid_pass(review, as_of):
            valid_pass_count += 1
        if review.expires_at_utc <= as_of:
            expired_count += 1
        review_generated_at = require_utc(review.generated_at_utc)
        latest_at = max(latest_at, review_generated_at) if latest_at else review_generated_at

    status = _research_status(
        review_count=len(unique_reviews),
        required_count=len(required_rows),
        missing_required_count=len(missing_required),
        expired_count=expired_count,
        valid_pass_count=valid_pass_count,
        latest_at=latest_at,
        as_of=as_of,
    )
    missing = []
    if research_reviews is None:
        missing.append("research_reviews")
    if handoff is None:
        missing.append("recommendation_handoff")

    return OperatorReportSection(
        key="research",
        title="Research",
        status=status,
        summary=(
            f"{len(unique_reviews)} deep research review(s); "
            f"{len(required_rows)} current row(s) require the gate."
        ),
        source_generated_at_utc=latest_at,
        items=[
            _item("Review count", len(unique_reviews)),
            _item("Valid research passes", valid_pass_count),
            _item("Expired reviews", expired_count, "needs_attention" if expired_count else "info"),
            _item("Rows requiring research", len(required_rows)),
            _item("Required rows missing review", len(missing_required)),
            _item("Review status counts", _counts_text(status_counts)),
        ],
        records=[
            {
                "symbol": review.symbol,
                "research_symbol": review.research_symbol,
                "status": review.status.value,
                "decision": review.decision.value if review.decision else None,
                "valid_pass": _review_is_valid_pass(review, as_of),
                "generated_at_utc": _iso(review.generated_at_utc),
                "expires_at_utc": _iso(review.expires_at_utc),
                "final_score": review.final_score,
                "warnings": _join(review.warnings),
            }
            for review in unique_reviews
        ],
        missing_data=missing + [f"research_review:{symbol}" for symbol in missing_required],
        warnings=_research_warnings(missing_required, expired_count, latest_at, as_of),
    )


def _preview_section(
    preview: RecommendationPreviewResponse | None,
    as_of: datetime,
) -> OperatorReportSection:
    if preview is None:
        return _missing_section(
            "preview",
            "Preview",
            "No recommendation preview sizing snapshot was supplied.",
            ["recommendation_preview"],
            warnings=[
                "Preview evidence is missing until an operator selects recommendation symbols."
            ],
        )

    generated_at = require_utc(preview.generated_at_utc)
    if preview.selected_count == 0:
        status: ReportStatus = "missing"
    elif preview.eligible_count == 0:
        status = "blocked"
    else:
        status = _freshness_status(generated_at, as_of)

    return OperatorReportSection(
        key="preview",
        title="Preview",
        status=status,
        summary=(
            f"{preview.selected_count} selected recommendation row(s), "
            f"{preview.eligible_count} eligible for preview-only sizing."
        ),
        source_generated_at_utc=generated_at,
        items=[
            _item("Mode", preview.mode),
            _item("Selected rows", preview.selected_count),
            _item("Eligible rows", preview.eligible_count),
            _item(
                "Total equity GBP",
                preview.total_equity_gbp,
                _value_status(preview.total_equity_gbp),
            ),
            _item("Estimated total cost GBP", preview.estimated_total_cost_gbp),
        ],
        records=[
            {
                "symbol": row.symbol,
                "research_symbol": row.research_symbol,
                "side": row.side,
                "eligible": row.eligible,
                "notional_gbp": row.estimated_notional_gbp,
                "cost_gbp": row.estimated_total_cost_gbp,
                "research_status": row.research_review_status,
                "blockers": _join(row.blockers),
                "warnings": _join(row.warnings),
            }
            for row in preview.rows
        ],
        missing_data=[] if preview.selected_count else ["selected_recommendation_symbols"],
        warnings=_stale_warning(generated_at, as_of, "Recommendation preview")
        + list(preview.warnings),
    )


def _pilot_paper_section(
    workflow: PilotPaperWorkflowSummary | None,
    as_of: datetime,
) -> OperatorReportSection:
    if workflow is None:
        return _missing_section(
            "pilot_paper",
            "Pilot Paper",
            "No pilot paper workflow snapshot was supplied.",
            ["pilot_paper_workflow"],
            warnings=[
                "Paper evidence is missing until preview rows are linked to a paper simulation."
            ],
        )

    generated_at = require_utc(workflow.generated_at_utc)
    status = _workflow_status(workflow.workflow_status)
    if status == "available":
        status = _freshness_status(generated_at, as_of)

    return OperatorReportSection(
        key="pilot_paper",
        title="Pilot Paper",
        status=status,
        summary=(
            f"Pilot workflow is {workflow.workflow_status}; "
            f"{workflow.simulated_fill_count} simulated fill row(s)."
        ),
        source_generated_at_utc=generated_at,
        items=[
            _item("Workflow status", workflow.workflow_status, status),
            _item("Expected vs simulated", workflow.expected_vs_simulated_status),
            _item("Simulated fills", workflow.simulated_fill_count),
            _item("Persistence status", workflow.persistence_status, "missing"),
            _item("Reconciliation status", workflow.reconciliation_status, "missing"),
            _item("Preview source hash", workflow.preview_source_hash),
            _item("Simulation hash", workflow.simulation_hash),
        ],
        records=[
            {
                "symbol": row.symbol,
                "research_symbol": row.research_symbol,
                "side": row.side,
                "preview_eligible": row.preview_eligible,
                "expected_notional_gbp": str(row.expected_notional_gbp),
                "simulated_status": row.simulated_status,
                "expected_vs_simulated_status": row.expected_vs_simulated_status,
                "blockers": _join(row.blockers),
                "warnings": _join(row.warnings),
            }
            for row in workflow.rows
        ],
        missing_data=["paper_persistence", "paper_reconciliation"],
        warnings=_stale_warning(generated_at, as_of, "Pilot paper workflow")
        + list(workflow.warnings),
    )


def _management_section(
    management: OperatorManagementStatus | None,
) -> OperatorReportSection:
    if management is None:
        return _missing_section(
            "management",
            "Management",
            "No management status snapshot was supplied.",
            ["management_status"],
        )

    if management.kill_switch_enabled:
        status: ReportStatus = "blocked"
        summary = "Kill switch is enabled; live workflows must remain blocked."
    elif management.runtime_mode == RuntimeMode.LIVE.value and management.live_armed:
        status = "needs_attention"
        summary = "Live mode is armed; require paper evidence and explicit operator approval."
    elif not management.broker_credentials_configured or not management.deep_research_configured:
        status = "partial"
        summary = "Management status has configuration gaps that block full pilot evidence."
    else:
        status = "available"
        summary = management.summary or "Preview-first management state is ready for review."

    missing = []
    if not management.broker_credentials_configured:
        missing.append("trading212_read_only_credentials")
    if not management.deep_research_configured:
        missing.append("openai_deep_research_key")
    warnings = []
    if management.live_armed:
        warnings.append("Live is armed in runtime state; report shell still submits nothing.")
    if management.kill_switch_enabled:
        warnings.append("Kill switch is enabled; keep live submission blocked.")

    return OperatorReportSection(
        key="management",
        title="Management",
        status=status,
        summary=summary,
        items=[
            _item("Runtime mode", management.runtime_mode, status),
            _item(
                "Live armed",
                management.live_armed,
                "needs_attention" if management.live_armed else "info",
            ),
            _item(
                "Kill switch enabled",
                management.kill_switch_enabled,
                "blocked" if management.kill_switch_enabled else "info",
            ),
            _item(
                "Broker credentials configured",
                management.broker_credentials_configured,
                _bool_available(management.broker_credentials_configured),
            ),
            _item(
                "Deep research configured",
                management.deep_research_configured,
                _bool_available(management.deep_research_configured),
            ),
            _item("Optional providers configured", management.optional_provider_count),
        ],
        missing_data=missing,
        warnings=warnings,
    )


def _missing_section(
    key: ReportSectionKey,
    title: str,
    summary: str,
    missing_data: list[str],
    *,
    warnings: list[str] | None = None,
) -> OperatorReportSection:
    return OperatorReportSection(
        key=key,
        title=title,
        status="missing",
        summary=summary,
        missing_data=missing_data,
        warnings=warnings or [],
    )


def _recommendation_records(
    recommendations: RecommendationsResponse,
) -> list[dict[str, ReportValue]]:
    return [
        {
            "symbol": row.candidate.symbol,
            "research_symbol": row.candidate.research_symbol,
            "source": row.candidate.source,
            "action": row.action.value,
            "composite_score": round(row.scores.composite, 4),
            "risk_flags": _join(row.risk_flags),
            "warnings": _join(row.warnings),
        }
        for row in recommendations.recommendations
    ]


def _research_status(
    *,
    review_count: int,
    required_count: int,
    missing_required_count: int,
    expired_count: int,
    valid_pass_count: int,
    latest_at: datetime | None,
    as_of: datetime,
) -> ReportStatus:
    if review_count == 0:
        return "missing" if required_count else "partial"
    if missing_required_count:
        return "partial"
    if expired_count:
        return "needs_attention"
    if latest_at is not None and _freshness_status(latest_at, as_of) == "stale":
        return "stale"
    if required_count and valid_pass_count == 0:
        return "blocked"
    return "available"


def _workflow_status(workflow_status: str) -> ReportStatus:
    if workflow_status == "ready_for_operator_review":
        return "available"
    if workflow_status == "needs_attention":
        return "needs_attention"
    if workflow_status == "blocked_before_paper":
        return "blocked"
    return "partial"


def _review_is_valid_pass(review: DeepResearchReview, as_of: datetime) -> bool:
    return (
        review.status.value == "AVAILABLE"
        and review.decision is not None
        and review.decision.value == "RESEARCH_PASSED"
        and require_utc(review.expires_at_utc) > as_of
    )


def _overall_status(sections: list[OperatorReportSection]) -> ReportStatus:
    statuses = {section.status for section in sections}
    for status in ["blocked", "needs_attention", "unavailable"]:
        if status in statuses:
            return status  # type: ignore[return-value]
    if "missing" in statuses or "stale" in statuses or "partial" in statuses:
        return "partial"
    return "available"


def _report_warnings(sections: list[OperatorReportSection]) -> list[str]:
    warnings = [
        "Operator report shell is evidence aggregation only; it is not a PDF export system.",
        "The report shell never submits broker orders or arms live trading.",
    ]
    for section in sections:
        if section.missing_data:
            warnings.append(f"{section.title} has missing data: {', '.join(section.missing_data)}.")
        warnings.extend(section.warnings)
    return _dedupe(warnings)


def _research_warnings(
    missing_required: list[str],
    expired_count: int,
    latest_at: datetime | None,
    as_of: datetime,
) -> list[str]:
    warnings: list[str] = []
    if missing_required:
        warnings.append(
            "Deep research is missing for required row(s): " + ", ".join(missing_required) + "."
        )
    if expired_count:
        warnings.append(f"{expired_count} deep research review(s) are expired.")
    if latest_at is not None:
        warnings.extend(_stale_warning(latest_at, as_of, "Deep research review"))
    return warnings


def _freshness_status(source_at: datetime, as_of: datetime) -> ReportStatus:
    return "stale" if as_of - require_utc(source_at) > STALE_AFTER else "available"


def _stale_warning(source_at: datetime, as_of: datetime, label: str) -> list[str]:
    if _freshness_status(source_at, as_of) != "stale":
        return []
    return [f"{label} is older than {int(STALE_AFTER.total_seconds() // 3600)} hours."]


def _markdown_report(
    generated_at: datetime,
    status: ReportStatus,
    sections: list[OperatorReportSection],
    warnings: list[str],
) -> str:
    lines = [
        "# Operator Report Shell",
        "",
        f"Generated at UTC: {_iso(generated_at)}",
        f"Status: {status}",
        "",
    ]
    if warnings:
        lines.extend(["Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    for section in sections:
        lines.extend(
            [
                f"## {section.title}",
                "",
                f"Status: {section.status}",
                "",
                section.summary,
                "",
            ]
        )
        if section.items:
            lines.extend(f"- {item.label}: {_display_value(item.value)}" for item in section.items)
            lines.append("")
        if section.missing_data:
            lines.append("Missing data: " + ", ".join(section.missing_data))
            lines.append("")
        if section.warnings:
            lines.extend("Warning: " + warning for warning in section.warnings)
            lines.append("")
        if section.records:
            lines.extend(_markdown_table(section.records))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _markdown_table(records: list[dict[str, ReportValue]]) -> list[str]:
    headers = list(records[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for record in records:
        lines.append(
            "| "
            + " | ".join(_escape_markdown(_display_value(record.get(header))) for header in headers)
            + " |"
        )
    return lines


def _item(
    label: str,
    value: ReportValue,
    status: ReportStatus | Literal["info"] = "info",
    detail: str | None = None,
) -> OperatorReportItem:
    return OperatorReportItem(label=label, value=value, status=status, detail=detail)


def _mode_value(mode: RuntimeMode | str) -> str:
    return mode.value if isinstance(mode, RuntimeMode) else str(mode)


def _value_status(value: object | None) -> ReportStatus | Literal["info"]:
    return "missing" if value is None else "info"


def _bool_available(value: bool) -> ReportStatus:
    return "available" if value else "missing"


def _counts_text(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}: {counts[key]}" for key in sorted(counts))


def _display_value(value: ReportValue) -> str:
    if value is None:
        return "missing"
    return str(value)


def _join(values: list[str]) -> str:
    return ", ".join(values)


def _iso(value: datetime) -> str:
    return require_utc(value).isoformat()


def _escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _dedupe(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warning for warning in warnings if warning))


def _has_secret(value: SecretStr | object | None) -> bool:
    if value is None:
        return False
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return bool(value)


def _optional_provider_count(settings: Settings) -> int:
    social_configured = all(
        [
            _has_secret(settings.reddit_client_id),
            _has_secret(settings.reddit_client_secret),
            _has_secret(settings.x_bearer_token),
        ]
    )
    return sum(
        [
            _has_secret(settings.alpha_vantage_api_key),
            _has_secret(settings.fmp_api_key),
            _has_secret(settings.fred_api_key),
            _has_secret(settings.companies_house_api_key),
            bool(settings.sec_user_agent),
            social_configured,
        ]
    )
