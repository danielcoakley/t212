"""Rule-based thesis decision engine."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from isa_system.enrichment.enrichment_packet import CandidateEnrichmentPacket
from isa_system.scoring.composite_score import CompositeScore
from isa_system.thesis.models import InvestmentDecision, ThesisStatus


class DecisionInput(BaseModel):
    """Inputs used by the rule-based decision engine."""

    model_config = ConfigDict(extra="forbid")

    conviction_score: float
    confidence_score: float
    data_quality_score: float
    current_price: float | None = None
    target_price: float | None = None
    max_buy_price: float | None = None
    stop_or_review_level: float | None = None
    upside_downside_ratio: float | None = None
    valuation_extreme: bool = False
    technical_setup_positive: bool = True
    unacceptable_catalyst_risk: bool = False
    catalyst_confirmation_needed: bool = False
    portfolio_improves: bool = True


class DecisionResult(BaseModel):
    """Decision result with status and rationale."""

    model_config = ConfigDict(extra="forbid")

    decision: InvestmentDecision
    status: ThesisStatus
    rationale: list[str]


class DecisionEngine:
    """Evaluate deterministic decision rules."""

    def decide(
        self,
        score: CompositeScore,
        packet: CandidateEnrichmentPacket | None,
        inputs: DecisionInput,
    ) -> DecisionResult:
        """Return the decision for a candidate thesis."""

        if self._buy_now(score, inputs):
            return DecisionResult(
                decision=InvestmentDecision.BUY_NOW,
                status=ThesisStatus.WATCHLIST_WAIT_ENTRY,
                rationale=["BUY_NOW rules passed; human review still required before any action."],
            )

        if self._wait_entry(score, inputs):
            return DecisionResult(
                decision=InvestmentDecision.WATCHLIST_WAIT_ENTRY,
                status=ThesisStatus.WATCHLIST_WAIT_ENTRY,
                rationale=[
                    "Thesis is strong but entry or risk/reward is not attractive enough now."
                ],
            )

        if self._wait_catalyst(score, inputs, packet):
            return DecisionResult(
                decision=InvestmentDecision.WATCHLIST_WAIT_CATALYST,
                status=ThesisStatus.WATCHLIST_WAIT_CATALYST,
                rationale=["Candidate is promising but needs catalyst or evidence confirmation."],
            )

        return DecisionResult(
            decision=InvestmentDecision.REJECT,
            status=ThesisStatus.REJECTED,
            rationale=["Rejected by rule-based quality, data, valuation, or risk/reward checks."],
        )

    def _buy_now(self, score: CompositeScore, inputs: DecisionInput) -> bool:
        return (
            score.total_score >= 75
            and inputs.conviction_score >= 70
            and inputs.data_quality_score >= 60
            and not inputs.valuation_extreme
            and inputs.technical_setup_positive
            and not inputs.unacceptable_catalyst_risk
            and (inputs.upside_downside_ratio or 0) >= 2.0
            and inputs.current_price is not None
            and inputs.max_buy_price is not None
            and inputs.current_price <= inputs.max_buy_price
            and inputs.portfolio_improves
        )

    def _wait_entry(self, score: CompositeScore, inputs: DecisionInput) -> bool:
        if score.total_score < 70:
            return False
        poor_entry = (
            inputs.current_price is not None
            and inputs.max_buy_price is not None
            and inputs.current_price > inputs.max_buy_price
        )
        weak_ratio = inputs.upside_downside_ratio is not None and inputs.upside_downside_ratio < 2.0
        return inputs.conviction_score >= 65 and (poor_entry or weak_ratio)

    def _wait_catalyst(
        self,
        score: CompositeScore,
        inputs: DecisionInput,
        packet: CandidateEnrichmentPacket | None,
    ) -> bool:
        return (
            score.total_score >= 60
            and inputs.data_quality_score >= 50
            and (inputs.catalyst_confirmation_needed or not packet or not packet.catalysts)
        )
