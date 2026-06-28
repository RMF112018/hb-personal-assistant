# Metric Provenance Map — Phase 9A.1

Every value in `computed_cpm_health` is **Application-computed CPM** (`evidence_class:
"application_computed_cpm"`). None derive from source-export critical/driving-path/float fields.
Source-export health stays on its own `/health-data` keys (`capabilities`, `quality_summary`,
`baseline_health_facts`, source critical-path analytics, etc.), separate and unchanged.

| Field | Source (read-only) | Basis |
| --- | --- | --- |
| `run_chain[kind].available/status/analysis_scope` | `ScheduleCpmReadService.cpm_summary().runs` (from `schedule_cpm_runs` rows) | `application_computed_cpm` |
| `counts.computed_activity_count` | criticality (or float) run row `computed_activity_count` | `application_computed_cpm` |
| `counts.computed_critical/near_critical/noncritical_activity_count` | criticality run row (pre-aggregated) | `application_computed_cpm` |
| `counts.longest_path_member_count` | criticality run row (pre-aggregated) | `application_computed_cpm` |
| `counts.critical/near_critical_float_threshold_days` | criticality run row | `application_computed_cpm` (computed thresholds) |
| `counts.negative/zero/high/classified_total_float_count` | new `float_risk_counts()` `GROUP BY` over `schedule_cpm_activity_results.computed_total_float` | `application_computed_cpm` |
| `counts.high_total_float_threshold_days` | module constant `HIGH_TOTAL_FLOAT_DAYS=44.0` | **product constant** (DCMA high-float convention), NOT derived |
| `longest_path_summary.*` | `cpm_longest_path().path` (from `schedule_cpm_paths`) | `application_computed_cpm` |
| `dcma_critical_path_metric.*` | `cpm_summary().dcma_critical_path` (Phase 7 read-only evaluator) | `application_computed_cpm` |
| `diagnostics_summary.*` | `cpm_diagnostics()` (from `schedule_cpm_diagnostics`) | `application_computed_cpm` |

## Guarantees enforced
- `dcma_critical_path_metric.source_critical_flags_used == false` (verbatim from the evaluator).
- `caveats` carries `computed_critical_outside_longest_path` whenever present — never hidden
  (real sample: 1312 computed-critical vs 45 on the longest path).
- The longest path is the **computed longest path** — never labeled true/P6/forensic critical path.
- No source-export fields are surfaced in the envelope (the computed `_ACTIVITY_WHITELIST`
  excludes `source_critical_flag`/`source_driving_path_flag`/imported float; this envelope exposes
  only run-row aggregates + the computed-float `GROUP BY`).
- `high_total_float_threshold_days` is surfaced beside the bucket so the threshold is explicit.

## Stale-capability reconciliation
The import capability still records `cpm_recalculation: "deferred"` (`schedule_import_service.py:527`).
This envelope reports **actual CPM run availability** instead; the capability writer is intentionally
unchanged in 9A.1 (out of scope — no source mutation).
