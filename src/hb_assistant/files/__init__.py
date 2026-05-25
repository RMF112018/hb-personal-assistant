"""File/attachment ingestion and link discovery (Phase 9).

Eligibility gates, controlled downloads (via GraphHttpClient), hashing, bounded parsing,
failure isolation, and persistence with full source linking.
"""

from .eligibility import EligibilityGate
from .downloader import ControlledDownloader
from .hasher import ContentHasher
from .router import ParserRouter
from .service import FileIngestionService

__all__ = [
    "EligibilityGate",
    "ControlledDownloader",
    "ContentHasher",
    "ParserRouter",
    "FileIngestionService",
]