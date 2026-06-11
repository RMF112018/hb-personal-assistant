# 07 — Usefulness Gate & Status

`daily_run.py` extends `stage_context["email_followup"]` with candidate_count, project_key_coverage,
review_required_count, raw_access_count, degraded.

New contradictions in `usefulness_gate.py` (backward-compatible — absent keys never fire):

- email_followup_stage_degraded — projection stage failed/degraded but run claims success.
- email_followup_project_coverage_low_no_review — email candidates exist, project coverage < 1.0, and
  nothing flagged for review.
- email_followup_raw_access_unaudited — raw access without audit events (never in pass 1).

Pre-existing email_rows_but_empty_followup_no_data_gap and the global
executive_source_ref_coverage_below_100 (new families are executive) still apply. Proven by four new
tests in `tests/test_phase_10_usefulness_gate.py`, including the legacy-context backward-compat case.
