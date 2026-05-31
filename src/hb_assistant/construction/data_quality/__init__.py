"""Data quality, canonical identity, and source-record map (Phase 07A).

Local-only builders and CLI surfaces for project identity backfill (Prompt 02),
source-system record mapping (Prompt 03), relationship diagnostics, coverage marts,
and gates. All operations are read-only against external systems by default; writes
require explicit --apply and are limited to local SQLite metadata (no raw bodies,
tokens, or external writeback).

Coverage counts and record mapping use existing ConstructionStore list_* + direct
connection queries (plus one reusable helper added in Prompt 03 for the high-volume
procore_live_records table). No raw content, no destructive changes.

See package policy in the Phase 07A implementation docs for matching rules,
confidence classes, and review-required conventions.
"""

from .project_identity import (
    ProjectIdentityBackfill,
    backfill_project_identity,
    load_pilot_project_descriptors,
)
from .source_record_map import (
    SourceRecordMapBuilder,
    build_source_record_map,
)
from .relationships import (
    RelationshipDiagnostics,
    diagnose_relationships,
)

__all__ = [
    "ProjectIdentityBackfill",
    "backfill_project_identity",
    "load_pilot_project_descriptors",
    "SourceRecordMapBuilder",
    "build_source_record_map",
    "RelationshipDiagnostics",
    "diagnose_relationships",
]
