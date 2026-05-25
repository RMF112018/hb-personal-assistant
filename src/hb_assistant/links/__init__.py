"""Source Link Registry (Phase 5).

Enforces that generated outputs are linked to source_records before persistence.
Implements the provenance/trust layer described in 07.
"""

from .registry import SourceLinkRegistry, ALLOWED_LINK_TYPES

__all__ = ["SourceLinkRegistry", "ALLOWED_LINK_TYPES"]
