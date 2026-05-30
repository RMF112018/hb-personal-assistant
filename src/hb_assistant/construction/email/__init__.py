"""Phase 06 operational email-intelligence services (read-only, metadata-only).

Higher-layer services that compose the read-only Graph mail client (``graph/``)
with the construction store + email policy/registry. Mailbox is never mutated;
the only writes are local SQLite source/sync/index rows.
"""

from __future__ import annotations

from .folder_discovery import (
    DiscoveredFolder,
    EmailFolderDiscovery,
    FolderDiscoveryResult,
)
from .message_indexer import (
    EmailMessageIndexer,
    IndexedFolder,
    IndexResult,
)

__all__ = [
    "DiscoveredFolder",
    "EmailFolderDiscovery",
    "EmailMessageIndexer",
    "FolderDiscoveryResult",
    "IndexResult",
    "IndexedFolder",
]
