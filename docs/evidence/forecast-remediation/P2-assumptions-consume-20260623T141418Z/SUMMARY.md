# P2 — Operator-assumptions consumption · Evidence

All proofs generated against **temporary SQLite DBs** (copied-DB evidence; the live managed
DB was never read or written by this script). Flag: `HB_FORECAST_ASSUMPTION_CONSUMPTION_ENABLED=1`.

## Files
- `flag_on_factors.json` — flag ON + assumptions: confidence-modifier + required-gate factors
  emitted, applied to a temp DB, parity proven. Note the `raises`→`booster` factor on the
  per-code scorecard, the `lowers`→`penalty` factor on the project scorecard, and the
  `required_assumption_unsatisfied:*` penalty + warning.
- `flag_off_noop.json` — flag-on-but-zero-assumptions planned output is **byte-identical** to the
  no-assumptions baseline (no phantom factors). This is the regression-safety proof.
- `persisted_factor_keys.json` — the factor keys actually written to
  `forecast_confidence_factors` in the temp output DB (proves persistence via the existing
  `apply_plan` writer; no schema change).

## Scope
Confidence modifiers + required-assumption gate in `decision_support_engine` only. Dollar
value-overrides are deferred to P2b. No schema change; no live-DB write. See ADR 301.

## Regression analysis (full forecast suite, apples-to-apples)

The forecast suite is known-red on `origin/main` (the gap-validation report assigns those
failures to P10). To isolate any P2-introduced regression:

- Baseline (clean main `d9523fa7`, full `-k forecast`): **85 failed**.
- P2 branch (full `-k forecast`): **86 failed**.
- Node-id diff surfaced only order/state-dependent subprocess tests, NOT P2 code:
  - `test_forecasting_db_evidence_package` + `test_forecasting_evidence_script_integration`
    fail **identically on clean main in isolation** — subprocess
    `ModuleNotFoundError: No module named 'pydantic'` from
    `scripts/generate_forecasting_db_complete_evidence...` (the "evidence-script subprocess
    interpreter" issue the gap report assigns to **P10**). The full-suite baseline only
    passed them due to test-ordering/state.
  - `test_phase_08c_financial_completeness` only failed in a worktree lacking `.venv`
    (its CLI subprocess resolves `.venv/bin/hb-assistant` relative to CWD); it passes once
    `.venv` is present, on both trees.
- The three P2 modules (`decision_support_engine`, `assumptions_repository`,
  `forecast_runtime_config`) are imported by **none** of the failing tests.
- P2's own tests + the decision-support `phase2b` suite: **14 passed**.

Conclusion: **zero regressions attributable to P2.**
