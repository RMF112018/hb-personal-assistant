# API Contract — Phase 9A.1

## Endpoint (unchanged route, additive response)
`GET /api/schedules/versions/{schedule_version_key}/health-data` now returns an **additive**
`computed_cpm_health` key alongside all existing source-export health keys. No new route, no removed
or renamed fields, no schema migration. Read-only (viewer role ok); project-scope mismatch → 404.

## `computed_cpm_health` envelope
Available (CPM runs exist):
```json
{
  "available": true,
  "evidence_class": "application_computed_cpm",
  "source_export_evidence": "separate",
  "run_chain": { "graph_diagnostics": {"available": true, "status": "...", "analysis_scope": "..."},
                 "forward_pass": {...}, "backward_pass": {...}, "float": {...},
                 "longest_path": {...}, "criticality": {...} },
  "counts": { "computed_activity_count": 1507, "computed_critical_activity_count": 1312,
              "computed_near_critical_activity_count": 1, "computed_noncritical_activity_count": 194,
              "longest_path_member_count": 45, "critical_float_threshold_days": 0.0,
              "near_critical_float_threshold_days": 10.0, "negative_total_float_count": 1308,
              "zero_total_float_count": 4, "high_total_float_count": 153,
              "classified_total_float_count": 1507, "high_total_float_threshold_days": 44.0 },
  "longest_path_summary": { "available": true, "path_id": "...", "activity_count": 45,
                            "relationship_count": 44, "path_duration": 429.0,
                            "path_total_float": -296.0, "start_activity_id": "...",
                            "end_activity_id": "..." },
  "dcma_critical_path_metric": { "available": true, "measurable": true,
      "basis": "application_computed_cpm", "source_critical_flags_used": false,
      "reason_codes": [], "caveats": ["computed_critical_outside_longest_path"], ... },
  "diagnostics_summary": { "available": true, "total_count": 52, "by_severity": {...},
                           "by_calculation_type": {...} },
  "missing_dependency_reasons": [],
  "links": { "computed_cpm": "/schedules/cpm?version=..." }
}
```

Unavailable (no CPM runs) — Schedule Health still loads on source-export evidence:
```json
{ "available": false, "reason": "no_computed_cpm",
  "evidence_class": "application_computed_cpm", "source_export_evidence": "separate",
  "run_chain": { "...all available:false..." },
  "missing_dependency_reasons": ["graph_diagnostics","forward_pass", ...],
  "links": { "computed_cpm": "/schedules/cpm?version=..." } }
```

Partial chain: `available:true` (≥1 run) with `missing_dependency_reasons` listing the absent kinds
and per-kind `run_chain[*].available:false`; float buckets stay `null` (not fabricated 0) until the
float/criticality run exists.

Resilience: the enrichment is wrapped fail-soft in the route — any unexpected CPM-side error
degrades `computed_cpm_health` to `{available:false, reason:"computed_cpm_error"}` and never breaks
the existing `/health-data` response.

## Real sample
`sample-health-response.json` — captured from the schema-89 evidence DB for
`tropical|1071|2026-06-23 08:00` via `create_app(db_path="/tmp/hb-schedule-cpm-evaluation.sqlite")`.
`computed_cpm_health.available:true`; counts/longest-path/DCMA all populated.

## Frontend type
`frontend/src/lib/api.ts`: `ComputedCpmHealth` (+ nested `ComputedCpmHealthCounts`,
`…LongestPath`, `…DcmaMetric`, `…Diagnostics`, `…RunStatus`) and optional
`ScheduleHealthData.computed_cpm_health`. No rendering yet (9A.2/9A.3).
