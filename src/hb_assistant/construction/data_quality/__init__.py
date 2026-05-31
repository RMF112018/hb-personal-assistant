"""Data quality, canonical identity, and source-record map (Phase 07A).

Local-only builders and CLI surfaces for project identity backfill (Prompt 02),
source-system record mapping (Prompt 03), relationship diagnostics (Prompt 04),
agent-ready query marts and indexes (Prompt 05), and gates. All operations are
read-only against external systems by default; writes require explicit --apply
and are limited to local SQLite metadata (no raw bodies, tokens, or external
writeback).

Prompt 05 adds four materialised read models (project coverage reuse + three new)
plus latency instrumentation for the eight target local-agent queries (target 500 ms).

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
from .marts import (
    MartBuilder,
    populate_agent_ready_query_marts,
)

__all__ = [
    "ProjectIdentityBackfill",
    "backfill_project_identity",
    "load_pilot_project_descriptors",
    "SourceRecordMapBuilder",
    "build_source_record_map",
    "RelationshipDiagnostics",
    "diagnose_relationships",
    "MartBuilder",
    "populate_agent_ready_query_marts",
]
