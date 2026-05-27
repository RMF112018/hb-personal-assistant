"""Construction-agent Markdown projections (manifests + receipts).

SQLite remains authoritative for sync state. The Markdown artifacts here are
recomputable projections only — re-rendering them from store state must yield
byte-identical output for identical inputs.
"""

from .models import (
    ProcessingReceipt,
    SourceManifest,
    SourceManifestEntry,
    SyncReceipt,
)
from .renderer import ManifestRenderer
from .service import ManifestService
from .vault_writer import (
    ConstructionVaultWriter,
    VaultRootNotConfigured,
)

__all__ = [
    "ProcessingReceipt",
    "SourceManifest",
    "SourceManifestEntry",
    "SyncReceipt",
    "ManifestRenderer",
    "ManifestService",
    "ConstructionVaultWriter",
    "VaultRootNotConfigured",
]
