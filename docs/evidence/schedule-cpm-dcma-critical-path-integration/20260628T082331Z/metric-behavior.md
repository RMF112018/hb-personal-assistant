# DCMA critical-path metric behavior

| Scenario | dcma_critical_path_test status | source-export metric | readiness available_cpm_recalculated |
|---|---|---|---|
| Source-only XER/MSP, no CPM attempted | not_measurable_requires_recalculation (reason: "available separately") | present (separate) | False |
| P6 derived-only | not_measurable_requires_recalculation | none | False |
| Computed CPM chain valid, all longest-path activities computed_critical | **available_app_cpm_recalculated** (basis application_computed_cpm) | present (separate) | True |
| CPM attempted but incomplete (e.g. forward only) | not_measurable_requires_recalculation (cpm_recalculation: attempted_incomplete; reason_codes list the missing deps) | present (separate) | False |
| CPM chain present but a longest-path activity is noncritical/unclassified/missing float | not_measurable_requires_recalculation (reason_codes: longest_path_not_computed_critical / longest_path_member_unclassified / …) | present (separate) | False |

## Payload fields added (evidence_json on dcma_critical_path_test)
measurable: method=application_computed_cpm, basis, cpm_recalculation=implemented, dependency_run_ids{forward,backward,float,longest_path,criticality}, longest_path_id, path_activity_count, longest_path_critical_activity_count, computed_critical_activity_count, caveats, source_critical_flags_used=false, source_export_evidence=separate.
attempted-incomplete: method=application_computed_cpm_attempted, cpm_recalculation=attempted_incomplete, dependency_run_ids, reason_codes, caveats, source_critical_flags_used=false.
