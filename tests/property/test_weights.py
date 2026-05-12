"""Property tests for weight constraints."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from isa_system.domain.models import TargetWeight
from isa_system.portfolio.constraints import cap_and_normalise


@given(
    st.lists(
        st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    )
)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_capped_weights_remain_long_only(values: list[float]) -> None:
    """Capped and normalised weights stay within limits."""

    weights = [TargetWeight(f"S{i}", value) for i, value in enumerate(values)]
    result = cap_and_normalise(weights, max_single_name_weight=0.1, cash_buffer=0.03)
    assert all(item.weight >= 0 for item in result)
    assert sum(item.weight for item in result) <= 0.9700000001
