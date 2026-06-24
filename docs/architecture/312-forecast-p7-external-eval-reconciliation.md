# 312 — Forecast P7: external eval completion (test + reconciliation)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P7 (final phase)
- Gap: #8 (external/operator forecast evaluation)

## Context

P7 was scoped by the 2026-06-23 gap-validation report
(`docs/evidence/forecast-model-gap-validation/20260623T080628Z/forecast-model-gap-validation-report.md`)
as: "build XLSX ingest + multi-project discovery for the external-forecast eval pipeline
(auto-live-projection deferred)."

Verification against `origin/main` before implementing showed that spec is **stale** — both items
already landed in the external-eval implementation since the report was written:

- **XLSX ingest is implemented and reachable.** `forecast_external_ingest.py`: `_detect_format`
  returns `"xlsx"` for `.xlsx` (raises for other extensions); `preview()` dispatches `fmt ==
  "xlsx"` → `_parse_xlsx()` via `openpyxl` (already a dependency, `openpyxl>=3.1`), capturing
  `sheet_names` and storing the untrusted source as `source.xlsx` in the isolated eval-root.
- **Multi-project eligibility/discovery is implemented and wired.**
  `src/hb_assistant/forecasting/project_eligibility.py`
  (`resolve_eligible_eval_projects`, `assert_eval_project_eligible`,
  `HB_FORECAST_EVAL_PROJECT_ALLOWLIST`, `forecast_projects` DB reads) is called by
  `forecast_external_eval_service.evaluate` (eligibility gate at l.134; discovery at l.419) and is
  unit-tested in `tests/test_forecasting_project_eligibility.py`.

The genuine remaining gap was **test coverage**, not features: `_parse_xlsx` had zero coverage
(every external-eval test fed CSV), and no test ran the full `evaluate()` pipeline for a second
(non-tropical) project — `tests/test_forecasting_external_fixture.py` covered fixtureproj
eligibility + ingest + mapping only.

This is a direct application of the standing lesson: *verify origin/main before claiming work is
missing*.

## Decision

P7 = **tests + reconciliation only; no production code change.**

1. **XLSX ingest test** (`tests/test_forecasting_external_fixture.py`):
   `test_external_forecast_xlsx_ingest_parses_sheet` builds a workbook with `openpyxl`, feeds it
   through `ForecastExternalIngestService.preview()`, and asserts the worksheet name is surfaced
   (CSV yields an empty sheet list — so this is xlsx-specific and non-vacuous), the header/rows are
   parsed, the source is stored as `source.xlsx` under the isolated eval-root, and the payload is
   redaction-clean.
2. **Second-project full-evaluate test** (same file):
   `test_external_forecast_fixtureproj_full_evaluate` runs ingest → `propose_mapping` →
   `evaluate(project_key="fixtureproj")` and asserts the run succeeded, `mapped_count >= 1`,
   `guardrails.no_live_db_write`, the eval record's `project_key == "fixtureproj"`, the per-run
   `eval.sqlite` + evidence package land only under the eval-root, the baseline DB's external
   tables stay empty (read-only), and the payload is redaction-clean. This closes the Gap-8
   "second project eval" acceptance criterion through the whole pipeline.
3. **Stale gap report left immutable.** It is a historical evidence artifact
   (`docs/evidence/**`); the correction is recorded in `REMEDIATION-PLAN.md` + this ADR + the P7
   evidence bundle, not by editing the report.

The optional FastAPI xlsx-route test was **skipped**: the xlsx-ness lives entirely in the ingest
layer now covered, and the HTTP route forwards `filename`/`content_b64` straight to the same
service (already exercised by CSV route tests) — a route xlsx test would be redundant churn.

## Consequences

- No `src/` production change; no new API/CLI surface (operator-deferred; the report also defers
  "auto-discovery" and "auto-live-projection"). No schema/migration/`table_count` change (V61
  tables already exist). No live-DB/external/secret surface → no sensitive-op gate.
- Both edited test files are already in `scripts/test-forecasting.sh` → no bundle-allowlist edit.
- **P7 is the final remediation phase.** On merge, P1–P10 + P9b + P7 are all landed and the
  forecast-model remediation is complete.
- Out of scope / still deferred: external-eval CLI command, an eligible-projects discovery
  endpoint, and auto-live-projection.
