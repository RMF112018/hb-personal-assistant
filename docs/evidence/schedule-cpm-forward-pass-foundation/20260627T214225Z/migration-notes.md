# Migration notes — V84

- LATEST_SCHEMA_VERSION 83 → 84; migration `v84_schedule_cpm_forward_pass_foundation` (additive only).
- New tables (CREATE TABLE IF NOT EXISTS, idempotent): `schedule_cpm_activity_results`, `schedule_cpm_relationship_results` (+ indexes; FK → schedule_cpm_runs).
- Additive columns on existing `schedule_cpm_runs` via column-existence-guarded reconcile (PRAGMA table_info → ALTER ADD COLUMN for missing only): calculation_type, schedule_start_anchor, schedule_start_anchor_source, computed_activity_count, blocked_activity_count. node_count/edge_count reused as activity/relationship counts (not duplicated).
- table_lifecycle_status_contract.json: table_count 473 → 475 + two V84 entries (family schedule_cpm_v84, operational_empty_expected); 23 count-assert test files bumped 473→475 in lockstep; test_lifecycle_contract_473 → _475.
- No destructive ops (no DROP, no column removal, no table rewrite).
- Proven this session: fresh migrate → version 84, both result tables present, all 5 run columns present; re-apply leaves version 84 (idempotent).
