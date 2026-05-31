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
from .email_classifier import (
    CLASSIFICATION_VERSION,
    EmailClassificationReport,
    EmailClassificationResult,
    EmailIntelligenceClassifier,
    EmailModelOutput,
    InvalidEmailModelOutputError,
    parse_and_validate_email_output,
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
from .obsidian_projection import (
    EmailObsidianProjector,
    EmailObsidianReport,
)
from .operational_validation import (
    OperationalValidationReport,
    run_operational_validation,
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
from .review_categories import (
    REVIEW_CATEGORIES,
    ReviewCategory,
    classify_review_categories,
    get_review_category,
)
from .review_router import (
    EmailBodyCaptureDecision,
    ReviewRouter,
    ReviewRoutingReport,
    ReviewRoutingSample,
)
from .thread_summary import (
    EmailThreadSummaryMaterializer,
    ThreadSummaryReport,
    ThreadSummarySample,
)

__all__ = [
    "CLASSIFICATION_VERSION",
    "REVIEW_CATEGORIES",
    "AttachmentAnalysis",
    "DiscoveredFolder",
    "DiscoveryReport",
    "EmailBodyCaptureDecision",
    "EmailClassificationReport",
    "EmailClassificationResult",
    "EmailFolderDiscovery",
    "EmailIntelligenceClassifier",
    "EmailMessageIndexer",
    "EmailModelOutput",
    "EmailObsidianProjector",
    "EmailObsidianReport",
    "EmailThreadSummaryMaterializer",
    "OperationalValidationReport",
    "FolderDiscoveryResult",
    "IndexResult",
    "IndexedFolder",
    "InvalidEmailModelOutputError",
    "MatchSignal",
    "ProjectDescriptor",
    "ProjectEmailDiscovery",
    "ProjectMatchSummary",
    "ProjectMatcher",
    "RelationshipCandidate",
    "RelationshipCandidateBuilder",
    "RelationshipReport",
    "ReviewCategory",
    "ReviewRouter",
    "ReviewRoutingReport",
    "ReviewRoutingSample",
    "ThreadSummaryReport",
    "ThreadSummarySample",
    "analyze_attachment",
    "classify_review_categories",
    "classify_text_sensitivity",
    "detect_drive_links",
    "get_review_category",
    "load_pilot_project_descriptors",
    "normalize_message",
    "parse_and_validate_email_output",
    "run_operational_validation",
]
