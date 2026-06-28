# UI Computed CPM Review Notes

## Schedule Version 1

- Schedule version key: tropical|1071|2026-06-23 08:00
- Project: tropical
- Computed CPM available in DB: yes
- Persisted CPM runs: graph_diagnostics, forward_pass, backward_pass, float, longest_path, criticality
- Initial UI state: showed "No computed CPM yet"
- Root cause of initial UI state: backend was started through uvicorn factory create_app() without explicit db_path; create_app() app.state.db_path was None
- Evidence backend resolution: restarted API using artifacts/run-evidence-api.py with create_app(db_path=/tmp/hb-schedule-cpm-evaluation.sqlite)
- Computed CPM available after explicit backend restart: yes — the page surfaced the run-chain, DCMA evidence, longest path, and computed activity table once the backend was started via artifacts/run-evidence-api.py with create_app(db_path=/tmp/hb-schedule-cpm-evaluation.sqlite). API summary returned available:true (artifacts/api-cpm-summary-sample.json; artifacts/debug-api-cpm-summary-explicit-db-runner.json).
- DCMA evidence status: measurable=true, status available_app_cpm_recalculated, basis application_computed_cpm, caveats [computed_critical_outside_longest_path], reason_codes [] (artifacts/dcma-computed-cpm-sample.json).
- Longest Path panel: showed the extracted path cpmrun_17f1ffb7fe59a4e341a046262ea2dee9_p01 with 45 activities (artifacts/api-cpm-longest-path-sample.json).
- Activity table: showed application-computed activity rows (1507 computed activities across forward/backward/float/criticality), using app-owned whitelisted fields only — no source critical/driving/float columns.
- Source-export separation: confirmed — source_critical_flags_used:false and source_export_evidence:"separate"; evidence_class application_computed_cpm. Source critical flags are not used for application-computed CPM.
- Notes: The only blocker to UI visibility was the create_app/db_path runtime binding (create_app() without db_path leaves app.state.db_path=None → available:false). This is a runtime/evidence-harness condition, not a CPM computation or frontend defect. Frontend validation: typecheck clean, ScheduleCpmPage.test.tsx 7/7, eslint on the 5 CPM files clean (artifacts/frontend-test-output.txt).
