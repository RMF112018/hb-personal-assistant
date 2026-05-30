"""Phase 06 operational email-intelligence services (read-only, metadata-only).

Higher-layer services that compose the read-only Graph mail client (``graph/``)
with the construction store + email policy/registry. Mailbox is never mutated;
the only writes are local SQLite source/sync/index rows.
"""

from __future__ import annotations

from .attachment_analyzer import (
    AttachmentAnalysis,
    analyze_attachment,
    classify_text_sensitivity,
    detect_drive_links,
)
from .folder_discovery import (
    DiscoveredFolder,
    EmailFolderDiscovery,
    FolderDiscoveryResult,
)
from .message_indexer import (
    EmailMessageIndexer,
    IndexedFolder,
    IndexResult,
    normalize_message,
)
from .project_discovery import (
    DiscoveryReport,
    ProjectEmailDiscovery,
    ProjectMatchSummary,
)
from .project_matcher import (
    MatchSignal,
    ProjectDescriptor,
    ProjectMatcher,
    load_pilot_project_descriptors,
)
from .relationship_builder import (
    RelationshipCandidate,
    RelationshipCandidateBuilder,
    RelationshipReport,
)

__all__ = [
    "AttachmentAnalysis",
    "DiscoveredFolder",
    "DiscoveryReport",
    "EmailFolderDiscovery",
    "EmailMessageIndexer",
    "FolderDiscoveryResult",
    "IndexResult",
    "IndexedFolder",
    "MatchSignal",
    "ProjectDescriptor",
    "ProjectEmailDiscovery",
    "ProjectMatchSummary",
    "ProjectMatcher",
    "RelationshipCandidate",
    "RelationshipCandidateBuilder",
    "RelationshipReport",
    "analyze_attachment",
    "classify_text_sensitivity",
    "detect_drive_links",
    "load_pilot_project_descriptors",
    "normalize_message",
]
