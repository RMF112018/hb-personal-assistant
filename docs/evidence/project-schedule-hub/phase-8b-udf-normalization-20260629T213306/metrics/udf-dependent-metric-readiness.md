# UDF-Dependent Metric Readiness

{
  "available": true,
  "project_key": "tropical",
  "version_key": "tropical|S1|2026-07-01",
  "metrics": {
    "window_start_accuracy": {
      "ready": true,
      "blockers": [],
      "partial_dimension_support": false
    },
    "window_finish_accuracy": {
      "ready": true,
      "blockers": [],
      "partial_dimension_support": false
    },
    "should_have_finished_status": {
      "ready": true,
      "blockers": [],
      "partial_dimension_support": false
    },
    "delay_analysis": {
      "ready": true,
      "blockers": [],
      "partial_dimension_support": false,
      "caveats": [
        "This metric is a schedule review cue only; it is not a causation, entitlement, responsibility, or compensability finding."
      ]
    },
    "critical_issues_category_model": {
      "ready": true,
      "blockers": [],
      "partial_dimension_support": false,
      "caveats": [
        "This metric is a schedule review cue only; it is not a causation, entitlement, responsibility, or compensability finding."
      ]
    }
  },
  "join_proof": {
    "available": true,
    "project_key": "tropical",
    "version_key": "tropical|S1|2026-07-01",
    "activity_count": 3,
    "udf_row_count": 39,
    "joined_udf_row_count": 39,
    "join_failure_count": 0,
    "join_success_rate": 1.0,
    "activities_with_udf_count": 3,
    "orphan_udf_examples": [],
    "deterministic_join_proven": true,
    "backend_derived": true
  },
  "sparsity_warnings": [],
  "backend_derived": true
}
