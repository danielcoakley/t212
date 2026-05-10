"""Stress helpers for cost assumptions."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from isa_system.portfolio.costs import CostAssumptions


def doubled_slippage(assumptions: CostAssumptions) -> CostAssumptions:
    """Return cost assumptions with doubled slippage."""

    return replace(assumptions, slippage_bps=assumptions.slippage_bps * Decimal("2"))
