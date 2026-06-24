# P7 — External forecast eval completion (test + reconciliation) — FINAL remediation phase

- Phase: forecast-model remediation **P7** (last phase)
- ADR: `docs/architecture/312-forecast-p7-external-eval-reconciliation.md`
- Gap: #8 (external/operator forecast evaluation)
- Scope: **tests + reconciliation only — no production code change.** No schema/migration/
  `table_count`/live-DB/external/CLI change → no sensitive-op gate.

## Stale-spec finding (verified against origin/main)

The 2026-06-23 gap report scoped P7 as "build XLSX ingest + multi-project discovery." Both already
landed in the external-eval implementation since:
- **XLSX ingest:** `forecast_external_ingest.py` `_detect_format` (`.xlsx`→`"xlsx"`) +
  `_parse_xlsx` (openpyxl, a dep) wired into `preview()`, capturing `sheet_names`, storing
  `source.xlsx`.
- **Multi-project eligibility/discovery:** `forecasting/project_eligibility.py`
  (`resolve_eligible_eval_projects`/`assert_eval_project_eligible`/`HB_FORECAST_EVAL_PROJECT_ALLOWLIST`/
  `forecast_projects` reads), wired into `forecast_external_eval_service.evaluate` (l.134 gate,
  l.419 discovery) and unit-tested in `tests/test_forecasting_project_eligibility.py`.

The real gap was **test coverage** — `_parse_xlsx` had none, and no test ran a full second-project
`evaluate()`. (Lesson: verify origin/main before claiming work missing.)

## What landed (tests only)

In `tests/test_forecasting_external_fixture.py` (already in the forecasting bundle):
1. `test_external_forecast_xlsx_ingest_parses_sheet` — openpyxl-built workbook through `preview()`;
   asserts the worksheet name is surfaced (xlsx-specific; CSV yields an empty sheet list), header/
   rows parsed, `source.xlsx` stored under the isolated eval-root, redaction-clean.
2. `test_external_forecast_fixtureproj_full_evaluate` — full ingest→map→`evaluate(project_key=
   "fixtureproj")`; asserts succeeded, `mapped_count>=1`, `no_live_db_write`, eval-record
   `project_key=='fixtureproj'`, per-run `eval.sqlite`+evidence package isolated to the eval-root,
   baseline DB external tables empty (read-only), redaction-clean.

Optional FastAPI xlsx route test **skipped** (xlsx-ness is entirely in the ingest layer now
covered; the HTTP path just forwards — redundant).

## Reconciliation

- Stale gap report left **immutable** (historical `docs/evidence/**`); correction in the ledger +
  ADR 312 + this bundle.
- Ledger: P9b carried `in-review`→`merged` (#123, `2cce1394`); P7 `pending`→`in-review`; changelog
  appended. On merge, **remediation is complete (P1–P10 + P9b + P7)**.

## Validation

See `validation.txt` / `new_tests.txt`. Forecasting bundle 0 failures; ruff clean on the edited
test file. No live DB / external systems touched (tests use the isolated synthetic eval-root +
read-only baseline DB).
