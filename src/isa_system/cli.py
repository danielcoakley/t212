"""Command-line entry points for local workflows."""

from __future__ import annotations

import argparse

from isa_system.smoke_test import main as smoke_main


def main() -> None:
    """Run a small command dispatcher."""

    parser = argparse.ArgumentParser(prog="isa-system")
    parser.add_argument("command", choices=["smoke"], help="Command to run.")
    args = parser.parse_args()
    if args.command == "smoke":
        smoke_main()
