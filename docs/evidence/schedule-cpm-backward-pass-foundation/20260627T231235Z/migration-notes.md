# Migration notes — V85

- LATEST_SCHEMA_VERSION 84 → 85; migration `v85_schedule_cpm_backward_pass_foundation`.
- **Additive COLUMNS only — no new tables.** table_lifecycle_status_contract.json table_count is UNCHANGED at 475; the 23 count-assert test files are untouched.
- schedule_cpm_activity_results +9 cols: computed_late_start/finish, late_start/finish_offset_days, backward_pass_status, backward_pass_notes_json, terminal_activity_flag, controlling_successor_activity_id, controlling_successor_relationship_id.
- schedule_cpm_relationship_results +4 cols: candidate_predecessor_late_start/finish, backward_relationship_calc_status, backward_relationship_calc_notes_json.
- schedule_cpm_runs +2 cols: schedule_finish_anchor, schedule_finish_anchor_source. (computed_activity_count/blocked_activity_count/diagnostic_count reused for late-date counts; node_count/edge_count reused as activity/relationship counts.)
- Applied via column-existence-guarded reconcile (PRAGMA table_info → ALTER ADD COLUMN for missing only); no source-field changes; no destructive ops.
- Proven this session: fresh migrate → version 85; all 9+4+2 columns present on the three tables; re-apply leaves version 85 (idempotent).
