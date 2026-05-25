"""File/attachment ingestion and link discovery (Phase 9 + Phase 10 selective).

Eligibility + relevance scoring (Phase 6 signals), approval gate, controlled streaming downloads,
hashing, bounded parsing (full matrix), failure isolation, source-linked persistence.
"""

from .eligibility import ApprovalGate, EligibilityGate
from .downloader import ControlledDownloader
from .hasher import ContentHasher
from .relevance import FileRelevanceScorer, RelevanceScore
from .router import ParserRouter
from .service import FileIngestionService

__all__ = [
    "ApprovalGate",
    "EligibilityGate",
    "ControlledDownloader",
    "ContentHasher",
    "FileRelevanceScorer",
    "RelevanceScore",
    "ParserRouter",
    "FileIngestionService",
]