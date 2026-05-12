"""End-to-end offline-capable portfolio intelligence orchestrator."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from isa_system.discovery.candidate_intake import CandidateIntakeService
from isa_system.discovery.finviz_screeners import load_finviz_screeners
from isa_system.discovery.models import Candidate
from isa_system.enrichment.enrichment_packet import EnrichmentService, load_fixture_enrichment
from isa_system.portfolio.holdings import PortfolioHolding
from isa_system.portfolio.rebalance import propose_rebalance_actions
from isa_system.reports.report_generator import ReportGenerator
from isa_system.reports.report_store import ReportStore
from isa_system.scoring.composite_score import CompositeScore
from isa_system.scoring.ranking import RankingService
from isa_system.settings import get_settings
from isa_system.thesis.models import Thesis, ThesisStatus
from isa_system.thesis.thesis_generator import ThesisGenerator
from isa_system.thesis.thesis_tracker import ThesisTracker
from isa_system.trading212.models import OrderPreviewRequest
from isa_system.trading212.order_preview import create_order_preview
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


class OrchestratorRun(BaseModel):
    """End-to-end run summary."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    status: str
    candidate_count: int = 0
    top10_symbols: list[str] = Field(default_factory=list)
    buy_now_symbols: list[str] = Field(default_factory=list)
    watchlist_symbols: list[str] = Field(default_factory=list)
    reject_symbols: list[str] = Field(default_factory=list)
    rebalance_proposals: list[dict[str, object]] = Field(default_factory=list)
    order_previews: list[dict[str, object]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PortfolioOrchestrator:
    """Run the full local portfolio intelligence workflow."""

    def run(
        self,
        *,
        use_fixtures: bool = True,
        write_artifacts: bool = True,
        artifact_dir: Path | None = None,
    ) -> OrchestratorRun:
        """Run the full pipeline and optionally write smoke artifacts."""

        started = now_utc()
        run_id = sha256_digest({"started_at_utc": started})[:20]
        settings = get_settings()
        artifact_dir = artifact_dir or Path(settings.artifacts_path) / "smoke"
        warnings: list[str] = []
        errors: list[str] = []

        discovery = CandidateIntakeService(screeners=load_finviz_screeners()).run(
            fixture_html_by_screener=_fixture_html() if use_fixtures else None
        )
        warnings.extend(discovery.warnings)
        packets = EnrichmentService().enrich_symbols(
            [candidate.symbol for candidate in discovery.candidates],
            fixture_data_by_symbol={
                candidate.symbol: load_fixture_enrichment(candidate.symbol)
                for candidate in discovery.candidates
            }
            if use_fixtures
            else None,
        )
        packets_by_symbol = {packet.symbol: packet for packet in packets}
        scores = RankingService().top_n(discovery.candidates, packets_by_symbol, limit=10)
        tracker = ThesisTracker()
        report_store = ReportStore()
        theses: list[Thesis] = []
        reports_markdown: dict[str, str] = {}
        for score in scores:
            packet = packets_by_symbol.get(score.symbol)
            thesis = ThesisGenerator().generate(score, packet)
            thesis = tracker.save(thesis)
            report = report_store.save(ReportGenerator().generate(thesis, score, packet))
            thesis = tracker.save(ReportGenerator().apply_to_thesis(thesis, report))
            theses.append(thesis)
            reports_markdown[score.symbol] = report.markdown

        proposals = propose_rebalance_actions(_example_holdings(), theses, cash_gbp=5_000)
        order_previews = [
            create_order_preview(
                OrderPreviewRequest(
                    symbol=proposal.symbol,
                    side="SELL" if proposal.proposal_type.value.startswith("SELL") else "BUY",
                    estimated_trade_value=proposal.estimated_trade_value or 0.0,
                    current_price=100.0,
                    currency="GBP",
                    target_weight=proposal.target_weight,
                )
            )
            for proposal in proposals
            if proposal.estimated_trade_value and proposal.estimated_trade_value > 0
        ]

        run = OrchestratorRun(
            run_id=run_id,
            started_at_utc=started,
            completed_at_utc=now_utc(),
            status="completed",
            candidate_count=len(discovery.candidates),
            top10_symbols=[score.symbol for score in scores],
            buy_now_symbols=[
                thesis.symbol for thesis in theses if thesis.decision.value == "BUY_NOW"
            ],
            watchlist_symbols=[
                thesis.symbol
                for thesis in theses
                if thesis.status
                in {ThesisStatus.WATCHLIST_WAIT_ENTRY, ThesisStatus.WATCHLIST_WAIT_CATALYST}
            ],
            reject_symbols=[
                thesis.symbol for thesis in theses if thesis.status == ThesisStatus.REJECTED
            ],
            rebalance_proposals=[proposal.model_dump(mode="json") for proposal in proposals],
            order_previews=[preview.model_dump(mode="json") for preview in order_previews],
            errors=errors,
            warnings=warnings,
        )
        if write_artifacts:
            _write_artifacts(
                artifact_dir,
                discovery.candidates,
                scores,
                theses,
                reports_markdown,
                run,
            )
        return run


def _fixture_html() -> dict[str, str]:
    fixture_dir = Path("tests/fixtures")
    return {
        "Elite GARP Compounders": (fixture_dir / "finviz_elite_garp.html").read_text(
            encoding="utf-8"
        ),
        "Hidden Compounders": (fixture_dir / "finviz_hidden_compounders.html").read_text(
            encoding="utf-8"
        ),
        "Post-Earnings Acceleration": (fixture_dir / "finviz_post_earnings.html").read_text(
            encoding="utf-8"
        ),
    }


def _example_holdings() -> list[PortfolioHolding]:
    return [
        PortfolioHolding(
            symbol="LEGACY",
            company_name="Legacy Holding",
            market_value=1_000,
            current_weight=0.05,
            sleeve="strategy",
            thesis_status=ThesisStatus.BROKEN.value,
            conviction_score=35,
            expected_upside_pct=3,
            downside_risk_pct=15,
        )
    ]


def _write_artifacts(
    artifact_dir: Path,
    candidates: Sequence[Candidate],
    scores: Sequence[CompositeScore],
    theses: list[Thesis],
    reports_markdown: dict[str, str],
    run: OrchestratorRun,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([candidate.model_dump(mode="json") for candidate in candidates]).to_csv(
        artifact_dir / "latest_candidates.csv",
        index=False,
    )
    pd.DataFrame([score.model_dump(mode="json") for score in scores]).to_csv(
        artifact_dir / "top10.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "symbol": thesis.symbol,
                "status": thesis.status.value,
                "decision": thesis.decision.value,
            }
            for thesis in theses
            if thesis.status
            in {ThesisStatus.WATCHLIST_WAIT_ENTRY, ThesisStatus.WATCHLIST_WAIT_CATALYST}
        ]
    ).to_csv(artifact_dir / "watchlist.csv", index=False)
    reports_dir = artifact_dir / "research_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for symbol, markdown in reports_markdown.items():
        (reports_dir / f"{symbol}.md").write_text(markdown, encoding="utf-8")
    (artifact_dir / "rebalance_proposals.json").write_text(
        json.dumps(run.rebalance_proposals, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "order_previews.json").write_text(
        json.dumps(run.order_previews, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "run_summary.json").write_text(
        run.model_dump_json(indent=2),
        encoding="utf-8",
    )
