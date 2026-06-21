# External Forecast Workflow Summary

- Eligibility provider: env allowlist → `forecast_projects.enabled` → defaults
- `resolve_eligible_eval_projects()` + DB-aware `assert_eval_project_eligible()`
- Eval isolation: per-run directory under eval root; `eval.sqlite` never live DB
- Operator doc: `docs/forecasting/external-forecast-evaluation-workflow.md`
- Tests: multi-project, disabled project, env override, forecast_projects discovery