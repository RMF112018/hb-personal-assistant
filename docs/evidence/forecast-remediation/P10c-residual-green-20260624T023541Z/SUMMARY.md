# P10c — residual green-up (evidence)

**Phase:** P10c (forecast-remediation gap #10) · **Stamp:** 20260624T023541Z · **Branch:** `feature/forecast-residual-green-p10c` off `origin/main@42d3ce0a`

## Result

`pytest -k forecast`: **35 → 0 failing** · **35 fixed** · **0 new regressions** (`regression_summary.txt`,
`fixed_node_ids.txt`). Combined with P10 PR1 (88→35), P10 takes the forecast suite **88 → 0**.

The 35 residual were pre-existing regressions PR1's Group-D fix unmasked (P4/P4b `project_key`/
project-config threading). Fixed via 4 root causes:

- **RC2 (CFR source, the core fix):** `forecast_db_config_backed_core.py` did not thread `project_key`
  into the generators. Added `project_key=project_key` to both `descriptor.run()` call sites (db- and
  file-backed) **and** to the probability descriptor's inner `_run` closure (which the plan-gate review
  caught — it had no `project_key` and would have broken the probability path); updated the
  `GeneratorDescriptor.run` signature comment. All 4 generator run-functions uniformly require
  `project_key`.
- **RC3 (test):** the 6 monkeypatched perturb callbacks (phase18 ×2, phase18a ×1, phase19 ×1,
  phase20 ×2 — one more than the review's 5) now accept and forward `project_key` to the captured
  real run.
- **RC1 (test fixture):** the comprehensive generator reads `project_name` + `project_display_name`
  via `load_project_config` and embeds them in `manifest.json`/`README.md`. The phase20 +
  phase20_stability synthetic configs are value-accurate mirrors of the real `config/projects/tropical.json`
  (file-backed runs read the real config; db-backed read the synthetic snapshot — they must match for
  byte-exact parity). P4b added those two embedded fields; the fixtures didn't mirror them. Set both
  to the real values (`"Tropical World Nursery Senior Living Facility"` / `"Tropical World Nursery"`),
  consistent with the already-mirrored `job_reference`/`forecast_period`. *(Not a `.get()` mask — the
  key is legitimately required and present in the real config.)*
- **RC4 (test, NOT a product revert):** `launcher/service.py._forecast_default_env()` returning `{}`
  is **intentional** (commit `7223dba6`: forecast roots are seeded into `forecast_runtime_config.json`
  by `ensure_forecast_managed_storage`; env injection no longer required). The 3 launcher tests
  asserted the removed injection — rewrote them to assert the child env carries no `HB_FORECAST_*`
  keys. Also corrected the now-stale `_child_env` docstring (docstring-only; no behavior change).

## Scope

8 files: 1 CFR-source (`forecast_db_config_backed_core.py`), 1 hb_assistant docstring
(`launcher/service.py`), 6 test files. No schema/migrator change, no behavior change (RC2 restores
intended `project_key` threading; RC4 is a docstring + stale-test fix), no live-DB write. Ruff: changed
files clean; CFR core lint count unchanged vs `main`.

## Files

- `regression_summary.txt` — 35→0, fixed=35, new=0.
- `fixed_node_ids.txt` — the 35 node-ids that flipped green.
