"""Run the Streamlit dashboard."""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """Launch Streamlit."""

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "src/isa_system/dashboard/app.py"], check=True
    )


if __name__ == "__main__":
    main()
