# Forecast UI — Phase 3 Run Center (closeout evidence)

Implementation Phase 3 (Product Phase F, first increment): an operator-triggered, isolated
**context→analysis** forecast generation, reusing the CFR Phase 9 controlled workflow via runtime
path injection. First write-bearing phase — writes confined to an isolated runs-root; reads the
source data_root read-only; no live-DB / live-data-root writes; no LLM; deterministic.

Stamp: `20260620T171415Z` (UTC).

| File | Proves |
|---|---|
| `git_state.txt` | Phase 3 changed-file set on the feature branch. |
| `real_generation_smoke.txt` | A REAL context→analysis run succeeded (8/8 checks), `no_live_writes: True`, **0 redaction leaks** in the payload; honest guardrails block. |
| `live_root_untouched_proof.txt` | Live data_root listing hash identical before/after the real run (UNCHANGED); output isolated to a temp runs-root outside the repo and the live root. |
| `db_schema_version.txt` | Live DB schema = 60, WAL = 0 bytes; file-mode generation performs no DB access. |
| `no_migration_no_cfr_proof.txt` | store/migrator unchanged (no migration); LATEST_SCHEMA_VERSION=60; zero CFR changes (the runner is reused via path injection, not edited). |
| `test_output.txt` | Backend run tests + app-shell allowlist green; ruff clean. |

## CFR integration
`construction_financial_review` is not installed in the hb_assistant venv; the run service injects the
subrepo `src` onto sys.path + PYTHONPATH (so the Phase 7 subprocess inherits it) before importing the
workflow. No install, no extra deps, no CFR edit. Fail-closed if the src is absent.

## Posture
First write-bearing phase. Writes go ONLY to an explicitly-configured isolated runs-root
(`HB_FORECAST_RUNS_ROOT`, never under the data root); the source `data_root` (`HB_FORECAST_DATA_ROOT`)
is a read-only input. Deferred: comprehensive/monthly/probability packages, background-job orchestration
(run tables v63), config editing, external eval, engines.

Evidence bundle, not a lifecycle package.
