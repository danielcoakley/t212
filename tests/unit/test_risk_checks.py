"""Tests for pre-trade risk checks."""

from __future__ import annotations

from isa_system.domain.enums import RuntimeMode
from isa_system.execution.risk_checks import check_kill_switch, check_live_arming


def test_kill_switch_blocks() -> None:
    """Kill switch check blocks trading."""

    assert not check_kill_switch(True).passed


def test_live_requires_arming() -> None:
    """Live mode is rejected unless armed."""

    assert not check_live_arming(RuntimeMode.LIVE, False).passed
    assert check_live_arming(RuntimeMode.LIVE, True).passed
