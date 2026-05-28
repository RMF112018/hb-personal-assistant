"""Construction-agent Markdown projections (manifests + receipts).

SQLite remains authoritative for sync state. The Markdown artifacts here are
recomputable projections only — re-rendering them from store state must yield
byte-identical output for identical inputs.
"""

from .canonical_adapter import (
    CanonicalDocumentCardInput,
    CanonicalSourceNotFound,
    CanonicalSourceRef,
)
from .models import (
    DocumentCard,
    ProcessingReceipt,
    ProjectCard,
    RegistryOverview,
    ReviewRequiredItem,
    ReviewRequiredNote,
    SourceManifest,
    SourceManifestEntry,
    SyncReceipt,
)
from .renderer import ManifestRenderer
from .service import DocumentCardPolicyError, ManifestService
from .vault_writer import (
    ConstructionVaultWriter,
    VaultRootNotConfigured,
)

__all__ = [
    "CanonicalDocumentCardInput",
    "CanonicalSourceNotFound",
    "CanonicalSourceRef",
    "DocumentCard",
    "ProcessingReceipt",
    "ProjectCard",
    "RegistryOverview",
    "ReviewRequiredItem",
    "ReviewRequiredNote",
    "SourceManifest",
    "SourceManifestEntry",
    "SyncReceipt",
    "ManifestRenderer",
    "ManifestService",
    "DocumentCardPolicyError",
    "ConstructionVaultWriter",
    "VaultRootNotConfigured",
]
