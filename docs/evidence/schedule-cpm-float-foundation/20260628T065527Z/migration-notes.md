# Migration notes — V86

- LATEST_SCHEMA_VERSION 85 → 86; migration `v86_schedule_cpm_float_foundation`.
- **Additive COLUMNS only — no new tables.** table_lifecycle_status_contract.json table_count UNCHANGED at 475; the 23 count-assert test files untouched.
- schedule_cpm_activity_results +10 cols: computed_total_float(+basis/status/notes_json), computed_free_float(+basis/status/notes_json), controlling_free_float_successor_activity_id, controlling_free_float_relationship_id.
- schedule_cpm_relationship_results +3 cols: free_float_candidate, free_float_candidate_status, free_float_candidate_notes_json.
- schedule_cpm_runs +3 cols: source_run_id, total_float_computed_count, free_float_computed_count. (computed_activity_count/blocked_activity_count/diagnostic_count reused.)
- Applied via column-existence-guarded reconcile (PRAGMA table_info → ALTER ADD COLUMN for missing only); no source-field changes; no destructive ops.
- Proven this session: fresh migrate → version 86; all 10+3+3 columns present; re-apply leaves version 86 (idempotent).
