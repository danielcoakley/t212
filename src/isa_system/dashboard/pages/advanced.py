"""Advanced diagnostic surfaces for developers and audit checks."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.pages import (
    audit_logs,
    catalysts,
    factor_attribution,
    holdings,
    rebalance_preview,
    valuation,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render legacy diagnostic modules behind one advanced page."""

    st.title("Advanced")
    st.caption(
        "These diagnostics support audit, data-quality checks, and development. The core "
        "operator workflow is Overview -> Screener -> Recommendations -> Deep Research -> "
        "Preview."
    )
    diagnostic = st.radio(
        "Diagnostic surface",
        [
            "Holdings",
            "Valuation",
            "Catalysts",
            "Legacy Rebalance",
            "Factor Attribution",
            "Audit Logs",
        ],
        horizontal=True,
    )
    st.divider()
    if diagnostic == "Holdings":
        holdings.render(snapshot)
    elif diagnostic == "Valuation":
        valuation.render(snapshot)
    elif diagnostic == "Catalysts":
        catalysts.render(snapshot)
    elif diagnostic == "Legacy Rebalance":
        rebalance_preview.render(snapshot)
    elif diagnostic == "Factor Attribution":
        factor_attribution.render(snapshot)
    else:
        audit_logs.render()
