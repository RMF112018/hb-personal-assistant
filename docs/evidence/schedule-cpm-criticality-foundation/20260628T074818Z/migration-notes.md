# Migration notes — V88

- LATEST_SCHEMA_VERSION 87 → 88; migration `v88_schedule_cpm_criticality_foundation`.
- **Additive COLUMNS only — no new tables.** table_lifecycle_status_contract.json table_count UNCHANGED at 477; the 23 count-assert test files untouched.
- schedule_cpm_activity_results +12 cols: computed_critical_flag, computed_near_critical_flag, computed_criticality_class/status/basis/notes_json, critical_float_threshold_days, near_critical_float_threshold_days, longest_path_member_flag, longest_path_sequence, longest_path_membership_basis/notes_json.
- schedule_cpm_runs +7 cols: critical_float_threshold_days, near_critical_float_threshold_days, computed_critical/near_critical/noncritical/unclassified_activity_count, longest_path_member_count. (diagnostic_count + source_run_id reused.)
- Applied via column-existence-guarded reconcile (PRAGMA table_info → ALTER ADD COLUMN for missing only); no source-field changes; no destructive ops.
- Proven this session: fresh migrate → version 88; all 12+7 columns present; re-apply leaves version 88 (idempotent); table_count unchanged (477).
