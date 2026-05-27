"""Construction-agent configuration surface (source registry, project identity)."""

from .loader import load_source_registry
from .models import (
    BaselineMode,
    BaselinePolicy,
    BaselineSnapshot,
    BaselineStatus,
    DefaultPolicies,
    FolderPolicies,
    IndexingDepth,
    MatchConfidence,
    MatchStatus,
    ProjectIdentity,
    ResolutionStatus,
    SourceKind,
    SourceLocation,
    SourceRegistry,
    SourceSystem,
)

__all__ = [
    "load_source_registry",
    "BaselineMode",
    "BaselinePolicy",
    "BaselineSnapshot",
    "BaselineStatus",
    "DefaultPolicies",
    "FolderPolicies",
    "IndexingDepth",
    "MatchConfidence",
    "MatchStatus",
    "ProjectIdentity",
    "ResolutionStatus",
    "SourceKind",
    "SourceLocation",
    "SourceRegistry",
    "SourceSystem",
]
