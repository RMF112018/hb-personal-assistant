"""Data quality, canonical identity, and source-record map (Phase 07A).

Local-only builders and CLI surfaces for project identity backfill, source-system
record mapping, relationship diagnostics, coverage marts, and gates. All operations
are read-only against external systems by default; writes require explicit --apply
and are limited to local SQLite metadata (no raw bodies, tokens, or external writeback).

See package policy in the Phase 07A implementation docs for matching rules,
confidence classes, and review-required conventions.
"""

from .project_identity import (
    ProjectIdentityBackfill,
    backfill_project_identity,
    load_pilot_project_descriptors,
)

__all__ = [
    "ProjectIdentityBackfill",
    "backfill_project_identity",
    "load_pilot_project_descriptors",
]
