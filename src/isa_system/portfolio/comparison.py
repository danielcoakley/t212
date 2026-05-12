"""Portfolio comparison and rebalance proposal service."""

from __future__ import annotations

from datetime import timedelta

from isa_system.portfolio.holdings import PortfolioHolding
from isa_system.portfolio.proposal_models import ProposalType, RebalanceProposal
from isa_system.portfolio.risk import PortfolioRiskConfig
from isa_system.thesis.models import InvestmentDecision, Thesis, ThesisStatus
from isa_system.utils.time import now_utc


class PortfolioComparisonService:
    """Compare candidate theses against holdings and propose review actions."""

    def __init__(self, risk_config: PortfolioRiskConfig | None = None) -> None:
        self.risk_config = risk_config or PortfolioRiskConfig()

    def review(
        self,
        *,
        holdings: list[PortfolioHolding],
        theses: list[Thesis],
        cash_gbp: float = 0.0,
    ) -> list[RebalanceProposal]:
        """Create rationale-based proposals without submitting orders."""

        proposals: list[RebalanceProposal] = []
        proposals.extend(self._holding_risk_actions(holdings))
        for thesis in theses:
            proposals.append(self._candidate_action(thesis, holdings, cash_gbp))
        return proposals

    def _holding_risk_actions(self, holdings: list[PortfolioHolding]) -> list[RebalanceProposal]:
        proposals: list[RebalanceProposal] = []
        for holding in holdings:
            if holding.thesis_status == ThesisStatus.BROKEN.value:
                proposals.append(
                    self._proposal(
                        ProposalType.SELL_THESIS_BROKEN,
                        holding.symbol,
                        "holding",
                        "Existing holding thesis is marked broken.",
                        holding.current_weight,
                        0.0,
                        holding.market_value,
                        "portfolio risk reduction",
                        "Removes a broken-thesis holding from review queue.",
                        65,
                    )
                )
            elif holding.thesis_status == ThesisStatus.TARGET_REACHED.value:
                proposals.append(
                    self._proposal(
                        ProposalType.SELL_TARGET_REACHED,
                        holding.symbol,
                        "holding",
                        "Existing holding reached target and should be reviewed for trim/sell.",
                        holding.current_weight,
                        max(0.0, holding.current_weight / 2),
                        holding.market_value / 2,
                        "position trim",
                        "Reduces exposure after target reached.",
                        60,
                    )
                )
        return proposals

    def _candidate_action(
        self,
        thesis: Thesis,
        holdings: list[PortfolioHolding],
        cash_gbp: float,
    ) -> RebalanceProposal:
        if thesis.decision == InvestmentDecision.WATCHLIST_WAIT_ENTRY:
            return self._watchlist(
                thesis, ProposalType.WATCHLIST_WAIT_ENTRY, "Entry is not attractive."
            )
        if thesis.decision == InvestmentDecision.WATCHLIST_WAIT_CATALYST:
            return self._watchlist(
                thesis,
                ProposalType.WATCHLIST_WAIT_CATALYST,
                "Catalyst confirmation is still needed.",
            )
        if thesis.decision != InvestmentDecision.BUY_NOW:
            return self._hold(thesis, "Candidate is not approved for buy review.")

        cooldown = self._cooldown_holding(thesis.symbol, holdings)
        if cooldown is not None:
            return self._hold(thesis, f"Cooldown active after recent trade in {cooldown.symbol}.")

        strategy_weight = sum(item.current_weight for item in holdings if item.sleeve == "strategy")
        if strategy_weight >= self.risk_config.max_strategy_sleeve_weight:
            return self._watchlist(
                thesis,
                ProposalType.WATCHLIST_WAIT_ENTRY,
                "Strategy sleeve allocation is already at or above limit.",
            )

        weakest = self._weakest_holding(holdings)
        if weakest and self._materially_superior(thesis, weakest):
            return self._proposal(
                ProposalType.REPLACE_WITH_CANDIDATE,
                thesis.symbol,
                "candidate",
                f"Candidate materially improves on weakest holding {weakest.symbol}.",
                weakest.current_weight,
                self.risk_config.default_new_position_weight,
                weakest.market_value,
                f"replace {weakest.symbol}",
                "Improves conviction and risk/reward if operator approves.",
                thesis.confidence_score,
            )

        if cash_gbp > self.risk_config.min_cash_buffer_gbp:
            trade_value = max(0.0, cash_gbp - self.risk_config.min_cash_buffer_gbp)
            return self._proposal(
                ProposalType.BUY_NEW,
                thesis.symbol,
                "candidate",
                "Candidate passed thesis rules and can be funded from available cash.",
                0.0,
                self.risk_config.default_new_position_weight,
                trade_value,
                "cash",
                "Adds a new reviewed position without selling an existing holding.",
                thesis.confidence_score,
            )

        return self._hold(thesis, "Existing holdings or cash remain superior; no churn proposed.")

    def _materially_superior(self, thesis: Thesis, holding: PortfolioHolding) -> bool:
        ratio = thesis.upside_downside_ratio or 0
        holding_ratio = _ratio(holding.expected_upside_pct, holding.downside_risk_pct)
        return (
            thesis.conviction_score
            >= holding.conviction_score + self.risk_config.material_conviction_delta
            and ratio >= holding_ratio + self.risk_config.material_ratio_delta
            and holding.thesis_status
            in {None, ThesisStatus.NEEDS_REVIEW.value, ThesisStatus.BROKEN.value}
        )

    def _weakest_holding(self, holdings: list[PortfolioHolding]) -> PortfolioHolding | None:
        if not holdings:
            return None
        return min(holdings, key=lambda holding: (holding.conviction_score, holding.current_weight))

    def _cooldown_holding(
        self,
        symbol: str,
        holdings: list[PortfolioHolding],
    ) -> PortfolioHolding | None:
        cutoff = now_utc() - timedelta(days=self.risk_config.cooldown_days)
        for holding in holdings:
            if (
                holding.symbol == symbol
                and holding.last_trade_at_utc is not None
                and holding.last_trade_at_utc >= cutoff
            ):
                return holding
        return None

    def _watchlist(
        self,
        thesis: Thesis,
        proposal_type: ProposalType,
        rationale: str,
    ) -> RebalanceProposal:
        return self._proposal(
            proposal_type,
            thesis.symbol,
            "candidate",
            rationale,
            0.0,
            None,
            0.0,
            None,
            "Keeps candidate researched but unbought.",
            thesis.confidence_score,
        )

    def _hold(self, thesis: Thesis, rationale: str) -> RebalanceProposal:
        return self._proposal(
            ProposalType.HOLD,
            thesis.symbol,
            "candidate",
            rationale,
            0.0,
            None,
            0.0,
            None,
            "Avoids unnecessary portfolio churn.",
            thesis.confidence_score,
        )

    def _proposal(
        self,
        proposal_type: ProposalType,
        symbol: str,
        candidate_or_holding: str,
        rationale: str,
        current_weight: float | None,
        target_weight: float | None,
        estimated_trade_value: float | None,
        funding_source: str | None,
        expected_impact: str,
        confidence_score: float,
    ) -> RebalanceProposal:
        return RebalanceProposal(
            proposal_type=proposal_type,
            symbol=symbol,
            candidate_or_holding=candidate_or_holding,
            rationale=rationale,
            target_weight=target_weight,
            current_weight=current_weight,
            estimated_trade_value=estimated_trade_value,
            funding_source=funding_source,
            expected_impact=expected_impact,
            risks=[
                "Manual approval required.",
                "No live order submission exists in this workflow.",
            ],
            manual_approval_required=True,
            confidence_score=round(confidence_score, 2),
            created_at_utc=now_utc(),
        )


def _ratio(upside: float | None, downside: float | None) -> float:
    if upside is None or downside is None or downside == 0:
        return 0.0
    return max(0.0, upside / abs(downside))
