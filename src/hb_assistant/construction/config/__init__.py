"""Construction-agent configuration surface (source registry, project identity)."""

from .loader import load_source_registry
from .models import (
    ProjectIdentity,
    ResolutionStatus,
    SourceKind,
    SourceLocation,
    SourceRegistry,
)

__all__ = [
    "load_source_registry",
    "ProjectIdentity",
    "ResolutionStatus",
    "SourceKind",
    "SourceLocation",
    "SourceRegistry",
]
