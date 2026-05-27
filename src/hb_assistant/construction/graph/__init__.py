"""Construction-agent Graph integration (read-only)."""

from .delta_crawler import ConstructionDeltaCrawler, CrawlReceipt
from .resolver import ConstructionGraphResolver, ResolutionResult

GRAPH_SCOPES_DRIVE = ["Files.ReadWrite.All", "User.Read"]
GRAPH_SCOPES_SITE_PAGE = ["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]
GRAPH_SCOPES = GRAPH_SCOPES_SITE_PAGE


def scopes_for_source_kind(kind: str) -> list[str]:
    """Return the minimal delegated Graph scope set for a source kind.

    Drive-/folder-scoped delta + drive-item metadata only need
    ``Files.ReadWrite.All`` (Files.Read would also work; we use the
    admin-consented superset). ``Sites.Read.All`` is only required when
    resolving SharePoint site pages (``sharepoint_site_page``) where
    page metadata and linked-library discovery hit ``/sites/{id}``.
    """
    if kind == "sharepoint_site_page":
        return list(GRAPH_SCOPES_SITE_PAGE)
    return list(GRAPH_SCOPES_DRIVE)


__all__ = [
    "ConstructionGraphResolver",
    "ResolutionResult",
    "ConstructionDeltaCrawler",
    "CrawlReceipt",
    "GRAPH_SCOPES",
    "GRAPH_SCOPES_DRIVE",
    "GRAPH_SCOPES_SITE_PAGE",
    "scopes_for_source_kind",
]
