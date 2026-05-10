"""Audit log dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render() -> None:
    """Render audit and status rows."""

    st.dataframe(
        pd.DataFrame(
            [{"actor": "system", "action": "startup", "outcome": "ok", "payload_hash": "synthetic"}]
        ),
        use_container_width=True,
    )
