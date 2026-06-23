# P10 PR1 — forecast-suite hardening (evidence)

**Phase:** P10 PR1 (gap #10, "high") · **Stamp:** 20260623T205408Z · **Branch:** `feature/forecast-test-hardening-p10` off `origin/main@c49ca031`

## Result

`pytest -k forecast`: **88 → 35 failing** · **53 fixed** · **0 new regressions** (`regression_summary.txt`,
`fixed_node_ids.txt`, `residual_node_ids.txt`).

## What PR1 changed (mechanical suite hardening)

- **Group D — CFR relative-import regression (P4b, `55b992ae`):** the 4 bare-file generators
  (`GENERATORS` in `cli.py`) ran a relative `from ..common.project_config import ...` inside a
  function reached under `__main__`, which fails when the script is executed as a bare file via
  subprocess. Converted to absolute imports (matching each file's own `sys.path` bootstrap +
  absolute-import convention): `analysis/generate_forecast_analysis_package.py:77`,
  `context/generate_forecast_context_package.py:109`, `analysis/generate_forecast_analysis_crosswalk_v2.py:80`,
  `mapping/generate_mapping_discrepancy_workpaper.py:67`. This unblocked the phase6–13 cascade.
- **Group E — P4 message stragglers (revealed by Group D):** 7 tests asserted the old
  `match="unsupported project_key"`; the eligibility refactor changed the message to
  `"...is not eligible; allowed: [...]"`. Updated each `match=` to `"not eligible"`.
- **Group B — stale schema_version asserts:** 6 forecast tests (phase10/11/12/13) hardcoded
  `schema_version == 61`; now import `LATEST_SCHEMA_VERSION` and assert against it (durable through
  P6's v72 bump). Left `test_forecast_runtime_config.py:219` untouched (intentional v61
  backward-compat fixture).
- **Group C — isolation leaks:** the 2 `unconfigured→503` tests deleted an env var but the resolver
  falls back to `managed_forecast_paths()`. Now monkeypatch the source-module resolver
  (`resolve_config_edit_root_value` / `resolve_eval_root_value`) to `None` so an unconfigured runtime
  is truly simulated regardless of the machine's persisted config.
- **Group A — evidence-script interpreter:** `scripts/generate_forecasting_db_complete_evidence.sh`
  used bare `python3` (no venv → `ModuleNotFoundError`). Now defaults `VENV_PYTHON` to the repo
  `.venv/bin/python` (overridable); the 2 evidence-script tests pass `VENV_PYTHON=sys.executable` /
  use `sys.executable` for their own subprocess.

No schema/migrator change, no v60+ migration, no hb_assistant product-code change. The Group-D fix is
a 4× one-line CFR-source bug fix (a P4b regression). Ruff: changed test files + script clean; the CFR
files' pre-existing lint-debt count is unchanged vs clean `main` (no new errors on changed lines).

## Residual — 35 failures (pre-existing, UNMASKED by Group D, NOT regressions)

All 35 were in the clean-`main` baseline (they previously died at the Group-D relative import before
reaching these deeper bugs; fixing Group D lets the tests run far enough to surface them). They are
**4 distinct, separate root causes** outside PR1's reviewed mechanical-hardening scope and span
multiple subsystems — deliberately NOT folded in (would be unreviewed multi-subsystem debugging):

1. **`KeyError: 'project_display_name'`** — `forecast_comprehensive/generate_comprehensive_forecast_package.py:702,752` subscripts a loaded project config that lacks the key (comprehensive + phase20_stability tests).
2. **`_run_comprehensive() missing keyword 'project_key'`** — `workflows/forecast_db_config_backed_core.py:483` signature drift (db-config-backed generation tests).
3. **perturb-callback `project_key` kwarg** — `forecast_{monthly,probability}_db_config_proof.py` pass `project_key` to a test-provided perturb callback that doesn't accept it (monthly/probability cli-mismatch + parity tests).
4. **`KeyError: 'HB_FORECAST_EVAL_ROOT'`** — `test_launcher_scheduler.py:1336` launcher env-default (automation domain, only tangentially forecast).

Recommended follow-up: a focused regression-fix PR (project_key threading + `project_display_name`
config key in the comprehensive/db-config generators; launcher env default). These are candidates for
a P10c or a dedicated fix; they are NOT forecast-correctness VALUE tests (PR2's scope).

## Files

- `regression_summary.txt` — baseline/branch/fixed/new counts.
- `fixed_node_ids.txt` — the 53 node-ids that flipped green.
- `residual_node_ids.txt` — the 35 still-failing node-ids (the 4 root causes above).
