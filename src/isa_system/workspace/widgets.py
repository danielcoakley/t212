"""OpenBB Workspace-compatible widget metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WorkspaceWidget(BaseModel):
    """Simple widget metadata for local backend consumption."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    endpoint: str
    type: str = "table"


def workspace_widgets() -> list[WorkspaceWidget]:
    """Return widget metadata for table-friendly local API outputs."""

    return [
        WorkspaceWidget(
            id="ranked-candidates",
            name="Ranked candidates",
            description="Latest scored and ranked candidates.",
            endpoint="/scores/latest",
        ),
        WorkspaceWidget(
            id="top10-research-queue",
            name="Top 10 research queue",
            description="Latest top 10 candidates for research.",
            endpoint="/candidates/top10",
        ),
        WorkspaceWidget(
            id="thesis-watchlist",
            name="Thesis watchlist",
            description="Tracked wait-entry and wait-catalyst theses.",
            endpoint="/thesis/watchlist",
        ),
        WorkspaceWidget(
            id="portfolio-holdings",
            name="Portfolio holdings",
            description="Current local holdings context.",
            endpoint="/portfolio/holdings",
        ),
        WorkspaceWidget(
            id="rebalance-proposals",
            name="Rebalance proposals",
            description="Manual-review rebalance proposal table.",
            endpoint="/rebalance/latest",
        ),
        WorkspaceWidget(
            id="risk-warnings",
            name="Risk warnings",
            description="Current portfolio intelligence risk warnings.",
            endpoint="/workspace/risk-warnings",
        ),
        WorkspaceWidget(
            id="research-reports",
            name="Research reports",
            description="Latest structured research report metadata.",
            endpoint="/research/reports/latest",
            type="markdown-list",
        ),
    ]
