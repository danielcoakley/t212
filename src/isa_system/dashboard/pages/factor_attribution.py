"""Factor attribution dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render() -> None:
    """Render factor attribution."""

    st.title("Factor Attribution")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "symbol": "MSFT",
                    "quality": 1.2,
                    "momentum": 0.8,
                    "value": -0.3,
                    "dividend_growth": 0.5,
                }
            ]
        ),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()
