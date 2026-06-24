# 305 — Forecast P10c: residual green-up (forecast suite 35 → 0)

- **Status:** Accepted (P10c; follows ADR 304 / P10 PR1)
- **Date:** 2026-06-24
- **Phase:** Forecast-model remediation P10 (gap #10) — the residual-fix follow-up to PR1.

## Context

P10 PR1 (ADR 304) took `pytest -k forecast` from 88 → 35 by fixing a P4b relative-import regression
(Group D) plus stale-assert / isolation / interpreter test debt. The 35 residual were **pre-existing
regressions PR1 unmasked** — those tests had been dying at the relative import before reaching deeper
`project_key`/project-config threading bugs introduced by P4/P4b. The user chose to fix them (P10c) to
green the suite before P10 PR2 (the correctness VALUE tests).

## Decision

Fix the 35 residual via 4 root causes; the only product/source change is restoring intended
`project_key` threading in the CFR core.

- **RC2:** `forecast_db_config_backed_core.py` — thread `project_key` into both `descriptor.run()`
  call sites and the probability descriptor's inner `_run` closure (all generator run-functions
  require it). Update the descriptor comment.
- **RC3:** update the 6 monkeypatched perturb callbacks to accept/forward `project_key`.
- **RC1:** make the phase20 / phase20_stability synthetic configs mirror the real `tropical.json`
  `project_name` + `project_display_name` (the comprehensive generator reads them via
  `load_project_config` and embeds them; file-backed reads the real config, db-backed the synthetic
  snapshot, so they must match for byte-exact parity — `job_reference`/`forecast_period` already
  mirror). Keep the generator strict (no `.get()` mask).
- **RC4:** the launcher's empty `_forecast_default_env()` is intentional (commit `7223dba6`); update
  the 3 stale launcher tests (assert no `HB_FORECAST_*` injection) and correct the stale `_child_env`
  docstring. **Not** a method restore.

Result: `-k forecast` **35 → 0**, 35 fixed, zero new regressions. P10 PR1 + P10c together: **88 → 0**.

## Consequences

- The forecast suite is green, giving P10 PR2 (forecast-correctness VALUE tests) a clean baseline.
- No schema/migrator change; no behavior change beyond restoring intended `project_key` threading.
  RC1/RC3/RC4 are test-fixture/test fixes; RC4 also fixes a stale docstring.
