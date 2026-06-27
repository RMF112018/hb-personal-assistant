# Migration notes — V83

- LATEST_SCHEMA_VERSION: 82 → 83 (verified against origin/main before edit).
- New migration: `v83_schedule_cpm_graph_diagnostics_foundation` (additive only).
- New tables (CREATE TABLE IF NOT EXISTS, idempotent):
  - `schedule_cpm_runs` — one summary row per graph-diagnostics run: node_count, edge_count,
    is_acyclic, diagnostic_count, topological_order_json, analysis_scope
    ('graph_diagnostics_only'), cpm_recalculation_status ('not_implemented').
  - `schedule_cpm_diagnostics` — one row per structural finding (FK → schedule_cpm_runs).
- Indexes: by schedule_version_key, project_key (runs); by cpm_run_id, schedule_version_key,
  activity_id (diagnostics).
- table_lifecycle_status_contract.json: table_count 471 → 473; added two entries with
  v="V83", lifecycle_status="operational_empty_expected".
- No destructive operations: no DROP, no column removals, no rewrite of existing tables.
- Idempotency verified: applying the migrator twice on a fresh DB leaves version 83 and the
  two tables intact.
