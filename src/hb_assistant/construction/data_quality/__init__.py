"""Data quality, canonical identity, and source-record map (Phase 07A).

Local-only builders and CLI surfaces for project identity backfill (Prompt 02),
source-system record mapping (Prompt 03), relationship diagnostics (Prompt 04),
agent-ready query marts and indexes (Prompt 05), gates and phase go/no-go (Prompt 07), Obsidian marker-bounded data-quality outputs (Prompt 06), and no-writeback / no-secret / no-raw-body safety proof (Prompt 08). All operations are
read-only against external systems by default; writes require explicit --apply
and are limited to local SQLite metadata (no raw bodies, tokens, or external
writeback).

Prompt 05 adds four materialised read models (project coverage reuse + three new)
plus latency instrumentation for the eight target local-agent queries (target 500 ms).

See package policy in the Phase 07A implementation docs for matching rules,
confidence classes, and review-required conventions.
"""

from .gates import (
    GateEvaluator,
    evaluate_data_quality_gates,
)
from .marts import (
    MartBuilder,
    populate_agent_ready_query_marts,
)
from .obsidian import (
    render_data_quality_obsidian_outputs,
)
from .phase_07d import (
    evaluate_phase_07d_data_quality_gates,
)
from .project_identity import (
    ProjectIdentityBackfill,
    backfill_project_identity,
    load_pilot_project_descriptors,
)
from .relationships import (
    RelationshipDiagnostics,
    diagnose_relationships,
)
from .safety import (
    build_data_quality_no_writeback_proof,
)
from .source_record_map import (
    SourceRecordMapBuilder,
    build_source_record_map,
)
from .table_inventory import (
    build_table_inventory_report,
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
    "render_data_quality_obsidian_outputs",
    "evaluate_data_quality_gates",
    "evaluate_phase_07d_data_quality_gates",
    "GateEvaluator",
    "build_data_quality_no_writeback_proof",
    "build_table_inventory_report",
]
