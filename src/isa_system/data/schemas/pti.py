"""Point-in-time schemas and joins."""

from __future__ import annotations

import pandas as pd

from isa_system.utils.time import ensure_utc_series

REQUIRED_FACT_COLUMNS = {"symbol", "fact_name", "value", "available_at_utc"}


def validate_pti_facts(facts: pd.DataFrame) -> pd.DataFrame:
    """Validate point-in-time fact rows."""

    missing = REQUIRED_FACT_COLUMNS.difference(facts.columns)
    if missing:
        raise ValueError(f"Missing PIT fact columns: {sorted(missing)}")
    out = facts.copy()
    out["available_at_utc"] = ensure_utc_series(out["available_at_utc"])
    if out["available_at_utc"].isna().any():
        raise ValueError("PIT facts contain missing available_at_utc values.")
    return out


def reject_future_information(facts: pd.DataFrame, as_of_utc: pd.Timestamp) -> None:
    """Reject facts that are not available at the rebalance timestamp."""

    valid = validate_pti_facts(facts)
    as_of = (
        pd.Timestamp(as_of_utc).tz_convert("UTC")
        if pd.Timestamp(as_of_utc).tzinfo
        else pd.Timestamp(as_of_utc, tz="UTC")
    )
    if (valid["available_at_utc"] > as_of).any():
        raise ValueError("Future information detected in point-in-time facts.")


def asof_join_facts(requests: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    """Join the latest available fact to each symbol/fact/as-of request."""

    valid = validate_pti_facts(facts)
    req = requests.copy()
    req["as_of_utc"] = ensure_utc_series(req["as_of_utc"])
    rows = []
    for item in req.to_dict("records"):
        subset = valid[
            (valid["symbol"] == item["symbol"])
            & (valid["fact_name"] == item["fact_name"])
            & (valid["available_at_utc"] <= item["as_of_utc"])
        ].sort_values("available_at_utc")
        if subset.empty:
            rows.append({**item, "value": pd.NA, "diagnostic": "missing_or_not_yet_available"})
        else:
            latest = subset.iloc[-1].to_dict()
            rows.append({**item, **latest, "diagnostic": "ok"})
    return pd.DataFrame(rows)
