# Final Handoff Template

Use this exact structure after implementation and validation.

```text
Commit summary

feat(second-brain): add daily brief effectiveness telemetry and ranking policy evaluation

Description

Manifest: phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package v1

Adds a deterministic, raw-safe, observational daily brief effectiveness layer.

- Schema V<version>: daily_brief_exposure_events, daily_brief_item_outcome_events,
  ranking_policy_eval_runs, ranking_policy_eval_items, model_profile_eval_results,
  brief_effectiveness_rollups.
- Adds packet builder, metric engine, ranking policy evaluator, model profile evaluator,
  Procore/source-family noise evaluator, rollup builder, and raw-free report renderer.
- Adds `hb-assistant second-brain daily-brief evaluate-effectiveness`.
- Dry-run writes zero rows; apply requires `--max-persist` and was validated only on
  a `/tmp` DB copy.
- Observational only: no lifecycle mutation, no source-ref mutation, no model autonomy,
  no external writeback.
- Reports accepted/rejected/snoozed/ignored rates, rank-outcome alignment, source-ref
  coverage, Procore noise, model degradation, model profile reliability, duplicate proxy,
  deterministic-vs-model delta, and feedback calibration lift with sample-size caveats.
- Evidence: docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/
- Validation:
  compile: <pass/fail>
  ruff: <pass/fail>
  mypy: <pass/fail>
  focused pytest: <pass/fail>
  no-raw-leak scan: <pass/fail>
  guard columns zero: <pass/fail>
  production DB SHA unchanged: <pass/fail>
- Known limitations:
  <none, or raw-free notes only>
```
