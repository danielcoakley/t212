"""Rationale-based rebalance proposal entry point."""

from __future__ import annotations

from isa_system.portfolio.comparison import PortfolioComparisonService
from isa_system.portfolio.holdings import PortfolioHolding
from isa_system.portfolio.proposal_models import RebalanceProposal
from isa_system.thesis.models import Thesis


def propose_rebalance_actions(
    holdings: list[PortfolioHolding],
    theses: list[Thesis],
    *,
    cash_gbp: float = 0.0,
) -> list[RebalanceProposal]:
    """Return manual-review rebalance proposals."""

    return PortfolioComparisonService().review(holdings=holdings, theses=theses, cash_gbp=cash_gbp)
