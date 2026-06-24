# P5 — Maturity / data-availability / confidence completion (Gap 5)

Evidence bundle for forecast-remediation **P5**. ADR 308.

## What shipped (pure derivation in decision_support_engine.py; NO migration / CFR / flag)

1. **M5 closeout + lifecycle_signal** — `_maturity_tier` gains M5 from output evidence (header
   `cost_to_complete / estimated_final_cost <= M5_CLOSEOUT_CTC_FRACTION` = 0.005, a ratio);
   `lifecycle_signal` populated via `_LIFECYCLE_SIGNAL` coded enum (was hardcoded None). ACCEPTED
   RISK (ADR 308): a stalled/exhausted project shows the same near-zero CTC and would read closeout.
2. **Output-aware availability** — commitment/schedule/changes/risk/probability/staffing flip to
   "available" when the run's v63 output tables have rows (two-hop join `child.output_id ->
   forecast_outputs`, scoped by run_id AND project_key); assumptions counted run-scoped from v66;
   owner+procore stay "unavailable" (no forecast backing table).
3. **completeness/mapping_quality/maturity/score** populated with deterministic count-derived ratios
   (no multi-metric blend); `GUARDRAILS["new_scoring_math"]` updated to name the count-derived
   availability score. Confidence-scorecard numeric score deferred.

## Validation
- `scripts/test-forecasting.sh` => 0 failing, 883 passed (876 + 7 new).
- `scripts/test-schedule.sh` => 0 failing.
- New `tests/test_forecast_p5_maturity_availability.py` (7 tests). Updated
  `test_forecast_decision_support_phase2b.py` availability count 7 -> 12.
- No live-DB write; temp/copied-DB only.

## Gates
- hb-implementation-plan-reviewer: REVISE -> all required changes incorporated (M5 named-constant
  on header CTC ratio + stall risk; two-hop join helper run_id+project_key; score = single
  count-derived ratio + guardrail string update; readmodel/coverage test updates).
- No sensitive-op gate (no migration/schema/live-DB).
