# 310 — Forecast P9: UI/API readiness + operator workflow (Gaps 1/5/6/7/9 surface)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P9
- Gap: surfaces #1/#5/#6/#7/#9 through the read-model + API + Run Center

## Context

The persisted forecast graph (v63 run-output + v66 decision-support) is browsed by the read-only
`ForecastRunReadModelService` + the `/api/forecast/db/*` routes + the Run Center React panels.
Earlier phases already surface most of the spec's list — `read_output` returns the header including
`variance_to_prior_forecast` + the change rows (assumption impact), and `read_decision_support`
returns maturity / availability / confidence / method-eligibility / model-selection (Gaps 5/6),
rendered by `ForecastDecisionSupportPanel`. What was **missing**: the P8 explainability narratives
(`forecast_output_narratives`, zero readers), a multi-project selector (the frontend hardcoded
`project = "tropical"`), and `variance_to_prior_forecast` in the *list* view.

**Scope split:** the spec's "move the gated live-write backup to a durable location" is a **sensitive**
change to the CFR gated live-DB write path; it is deferred to **P9b** (separate PR + sensitive-op
gate). **P9 is read-only UI/API only — no schema, no migration, no live-DB path, no sensitive-op gate.**

## Decision

1. **`read_narratives(output_id)` (read-model).** Mirrors `read_decision_support` but the business
   content lives in each row's `raw_json`, so it `json.loads` and emits a **per-scope curated**
   projection (`_curate_narrative`, whitelist via `_NARRATIVE_FIELDS`) — never `raw_json` verbatim.
   - **Redaction:** stamp-format structured fields (`forecast_period`, `accuracy_package_stamp`,
     `prior_run_id`) are dropped by omission; `applied_utc` is surfaced only as a friendly display.
     Critically, the P8 free-text `narrative` string itself embeds stamps (`source_qa` → "forecast
     period <stamp>", `lineage` → "prior_run=<stamp>"), so `_redact_stamps` scrubs the `run_stamp`
     pattern (`\d{8}_\d{6}` → `[redacted]`) on **every** emitted narrative. sha256 hex (64 chars) is
     leak-safe and surfaced. Unknown scope → `None` (fail-safe: emit nothing, never dump raw_json).
2. **`list_projects()` + `variance_to_prior_forecast` in `list_outputs`.** A `SELECT DISTINCT
   project_key … GROUP BY` with output counts powers the multi-project selector; the prior-delta
   column (already on the header) is added to the list view for parity with the detail.
3. **API.** Two new **viewer-role** GETs reusing the existing `_forecast_readmodel_service()` factory
   + `_forecast_readmodel_call()` wrapper (404-on-unknown-output): `GET /api/forecast/db/projects`
   (declared before the parameterized `/db/projects/{project_key}/…`) and
   `GET /api/forecast/db/outputs/{output_id}/narratives`.
4. **Frontend.** New `ForecastNarrativesPanel` (project totals, human-override audit table, source-QA
   advisory, lineage sha chips) mirroring `ForecastDecisionSupportPanel`. `ForecastDecisionSupportPanel`
   and `ForecastOperatorAssumptionsPanel` are prop-ified (`project: string`, replacing the hardcoded
   `tropical` incl. query keys + the operator-write mutation calls). `ForecastRunCenterPage` adds a
   project selector (shown when >1 project has outputs) and threads `project` into all three panels.

## Consequences

- One PR, **no schema/migration/`table_count` change, no live-DB write, no external system, no CFR
  source change** → no sensitive-op gate. All DB access is `mode=ro` via the existing read-model.
- Tests: `tests/test_fastapi_forecast_run_readmodel.py` extended (narratives with stamp bait in both
  structured fields AND the free-text narrative, `list_projects`, narratives 404, prior-delta in
  list) — `find_redaction_leaks` is the no-raw-leak backstop. New vitest
  `ForecastNarrativesPanel.test.tsx` + a page-level multi-project-selector test.
- Deferred: **P9b** durable live-write backup relocation (sensitive); maturity/availability/model
  surfacing (already shipped P5/P6); the confidence numeric score (deferred since P5).
