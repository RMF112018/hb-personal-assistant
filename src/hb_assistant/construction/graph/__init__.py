"""Construction-agent Graph integration (read-only)."""

from .delta_crawler import ConstructionDeltaCrawler, CrawlReceipt
from .resolver import ConstructionGraphResolver, ResolutionResult

GRAPH_SCOPES = ["Sites.Read.All", "Files.Read.All", "User.Read"]

__all__ = [
    "ConstructionGraphResolver",
    "ResolutionResult",
    "ConstructionDeltaCrawler",
    "CrawlReceipt",
    "GRAPH_SCOPES",
]
