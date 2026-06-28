# CPM read API contract (Phase 8, read-only)

All under `/api/schedules/versions/{schedule_version_key}`; `X-HB-UI-Role: viewer|operator|admin` (read; no operator gate). Unknown version → 404; missing CPM → 200 with `available:false`. No mutation endpoints.

## GET /cpm/summary
`{schedule_version_key, available, runs:{graph_diagnostics, forward_pass, backward_pass, float, longest_path, criticality -> {available, cpm_run_id, calculation_type, cpm_recalculation_status, analysis_scope, source_run_id, created_at, diagnostic_count, computed_activity_count}}, dcma_critical_path:{available, measurable, basis, dependency_run_ids, path_id, *_count, reason_codes, caveats, source_critical_flags_used:false}, missing_dependency_reasons, evidence_class:"application_computed_cpm", source_export_evidence:"separate"}`

## GET /cpm/activities?limit&offset
`{schedule_version_key, available, source_run:{cpm_run_id, calculation_type}, activities:[app-owned whitelist only], total_count, limit, offset, truncated}` — latest run by precedence criticality→float→backward→forward; NO source fields.

## GET /cpm/longest-path
`{schedule_version_key, available, path:{path_id, path_type, path_status, path_basis, start/end_activity_id, counts, durations/offsets, path_total_float}, activities:[ordered membership]}`

## GET /cpm/diagnostics
`{schedule_version_key, available, diagnostics:[{cpm_run_id, calculation_type, severity, diagnostic_type, summary, activity_id, relationship_ref}], total_count}`

## Guarantees
Read-only (no CPM run created/mutated — proven by test); source-export/proxy evidence not surfaced here (separate on Schedule Health); application-computed vs source-export clearly separated via evidence_class + source_critical_flags_used:false.
