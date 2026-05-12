# Workspace Integration

This project does not build a custom charting frontend. OpenBB Workspace should
remain the research and charting frontend.

## Startup

1. Start OpenBB API on `http://127.0.0.1:6900`.
2. Optionally start OpenBB MCP on `http://127.0.0.1:8001`.
3. Start this API on `http://127.0.0.1:8002`.
4. Read widget metadata from `http://127.0.0.1:8002/workspace/widgets.json`.

## Widgets

The widget metadata exposes table-friendly endpoints for:

- Ranked candidates
- Top 10 research queue
- Thesis watchlist
- Portfolio holdings
- Rebalance proposals
- Risk warnings
- Research reports

Use OpenBB Workspace for charts and visual research. Use this API for portfolio
intelligence outputs and audit-friendly local workflow state.
