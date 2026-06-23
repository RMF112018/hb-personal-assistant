# 304 — Forecast P10: forecast-correctness & isolation test hardening

- **Status:** Accepted (PR1 of 2)
- **Date:** 2026-06-23
- **Phase:** Forecast-model remediation P10 (gap #10, "high")
- **Relates:** P4/P4b (the regressions this PR repairs); the gap report §Phase 10 / §2.

## Context

The forecast suite was known-red (~88 `pytest -k forecast` failures on `main`) and asserts no
forecast VALUES. The gap report scopes P10 as two PRs: **(PR1)** suite hardening, **(PR2)**
forecast-correctness VALUE tests. This ADR covers PR1.

Investigation found the dominant failure was **not environmental**: P4b (`55b992ae`) introduced a
relative import (`from ..common.project_config import ...`) into the 4 bare-file generators, which
fails when those scripts run as `__main__` via subprocess — cascading across phase6–13. It had been
masked as generic "known-red" noise.

## Decision (PR1 — mechanical suite hardening)

- **Group D:** convert the relative import to absolute in all 4 `GENERATORS` scripts (consistent with
  each file's existing `sys.path` bootstrap + absolute-import design). Fixes the cascade; no runner /
  `-m` / PYTHONPATH change.
- **Group E (revealed by D):** update 7 tests asserting the old `"unsupported project_key"` message to
  the current `"not eligible"` eligibility message.
- **Group B:** 6 forecast tests track `LATEST_SCHEMA_VERSION` instead of a hardcoded `== 61`; the one
  intentional v61 backward-compat fixture (`test_forecast_runtime_config.py:219`) is left untouched.
- **Group C:** monkeypatch the source-module root resolvers to `None` so the 2 `unconfigured→503`
  tests simulate an unconfigured runtime regardless of the machine's persisted config.
- **Group A:** the evidence script uses the repo venv interpreter (`VENV_PYTHON`), not bare `python3`.

Result: `pytest -k forecast` 88 → 35 failing, 53 fixed, **zero new regressions**.

## Non-goals / residual

- The remaining 35 failures are **pre-existing** (in the baseline) and were **unmasked** (not caused)
  by the Group-D fix. They are 4 distinct, multi-subsystem root causes — `project_display_name`
  KeyError in the comprehensive generator; `_run_comprehensive()` missing `project_key`; proof-harness
  perturb callbacks not accepting `project_key`; launcher `HB_FORECAST_EVAL_ROOT` default — outside
  PR1's reviewed mechanical-hardening scope. They are documented (evidence bundle) for a focused
  follow-up, not silently absorbed and not bundled into PR1.
- No schema/migrator change, no hb_assistant product-code change, no live-DB write. The Group-D fix is
  a 4× one-line CFR-source bug fix.

## Consequences

- A coherent, low-risk hardening pass that more than halves the red forecast suite and repairs a real
  P4b regression, with zero regressions. PR2 will add the forecast-correctness VALUE tests
  (header == per-code Decimal sum, prior-delta, assumption consumption, P50 bands, multi-project).
