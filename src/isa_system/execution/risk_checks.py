"""Reusable pre-trade risk checks."""

from __future__ import annotations

from decimal import Decimal

from isa_system.domain.enums import RuntimeMode
from isa_system.domain.models import RiskCheckResult


def check_live_arming(mode: RuntimeMode, live_armed: bool) -> RiskCheckResult:
    """Ensure live submit is explicitly armed."""

    if mode == RuntimeMode.LIVE and not live_armed:
        return RiskCheckResult("live_armed", False, "Live trading is not armed.")
    return RiskCheckResult("live_armed", True, "Live mode state is acceptable.", severity="info")


def check_kill_switch(kill_switch_enabled: bool) -> RiskCheckResult:
    """Block orders when the kill switch is enabled."""

    if kill_switch_enabled:
        return RiskCheckResult("kill_switch", False, "Kill switch is enabled.")
    return RiskCheckResult("kill_switch", True, "Kill switch is clear.", severity="info")


def check_max_estimated_cost(cost: Decimal, threshold: Decimal) -> RiskCheckResult:
    """Reject an order batch when estimated costs are too high."""

    if cost > threshold:
        return RiskCheckResult(
            "max_estimated_cost", False, "Estimated costs exceed the configured threshold."
        )
    return RiskCheckResult(
        "max_estimated_cost", True, "Estimated costs are within threshold.", severity="info"
    )
