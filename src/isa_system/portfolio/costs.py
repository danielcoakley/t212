"""Transaction-cost model including configurable UK SDRT and FX cost."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostAssumptions:
    """Cost model assumptions in basis points or rates."""

    commission_bps: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("15")
    fx_spread_bps: Decimal = Decimal("15")
    uk_sdrt_rate: Decimal = Decimal("0.005")


@dataclass(frozen=True)
class InstrumentCostFlags:
    """Instrument-level tax and FX flags."""

    currency: str
    country: str
    asset_type: str = "STOCK"
    sdrt_applicable: bool | None = None


class CostModel:
    """Rule-based transaction cost estimator."""

    def __init__(self, assumptions: CostAssumptions | None = None) -> None:
        self.assumptions = assumptions or CostAssumptions()

    def estimate(
        self, notional_gbp: Decimal, *, side: str, instrument: InstrumentCostFlags
    ) -> Decimal:
        """Estimate transaction cost in GBP."""

        commission = notional_gbp * self.assumptions.commission_bps / Decimal("10000")
        slippage = notional_gbp * self.assumptions.slippage_bps / Decimal("10000")
        fx = Decimal("0")
        if instrument.currency.upper() not in {"GBP", "GBX"}:
            fx = notional_gbp * self.assumptions.fx_spread_bps / Decimal("10000")
        sdrt = Decimal("0")
        if side.upper() == "BUY" and self.is_sdrt_applicable(instrument):
            sdrt = notional_gbp * self.assumptions.uk_sdrt_rate
        return (commission + slippage + fx + sdrt).quantize(Decimal("0.0001"))

    def is_sdrt_applicable(self, instrument: InstrumentCostFlags) -> bool:
        """Return whether the UK SDRT rule should apply."""

        if instrument.sdrt_applicable is not None:
            return instrument.sdrt_applicable
        return instrument.country.upper() == "GB" and instrument.asset_type.upper() == "STOCK"
