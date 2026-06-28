# Migration notes — V87

- LATEST_SCHEMA_VERSION 86 → 87; migration `v87_schedule_cpm_longest_path_foundation`.
- **TWO new tables** (path summary is a separate analysis artifact): schedule_cpm_paths, schedule_cpm_path_activities (+ indexes; FKs → schedule_cpm_runs / schedule_cpm_paths). table_lifecycle_status_contract.json table_count **475 → 477** + 2 entries (family schedule_cpm_v87); the 23 count-assert test files bumped 475→477 in lockstep; test_lifecycle_contract_475 → _477.
- schedule_cpm_runs +5 cols (column-existence-guarded reconcile): path_count, longest_path_activity_count, longest_path_relationship_count, longest_path_duration, longest_path_end_activity_id. (source_run_id from V86 reused for the float run id.)
- No new relationship_results columns (path membership lives in the new tables). No source-field changes; no destructive ops.
- Proven this session: fresh migrate → version 87; both new tables present + all 5 run columns; re-apply leaves version 87 (idempotent).
