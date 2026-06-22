# ADR 294 — Make the accuracy gate faithful: reconstruct procore_progress (5/6 methods) + coverage disclosure

- **Status:** Accepted
- **Date:** 2026-06-22
- **Phase:** Forecast production-readiness (accuracy-gate fidelity)
- **Builds on:** ADR 288 (accuracy gate), 290 (faithful reliabilities/trend), 293 (damping monotonic-down).

## Context

The accuracy gate's reconciled backtest — the evidence every forecast-trust decision rests on —
reconstructed only **4 of production's 6 independent methods** (owner_progress, trend, commitment,
cpi). It omitted `procore_progress_eac` and `schedule_remaining_work_eac`. That blind spot is why the
damping flip surprised us: `procore_progress` was the **$17.9M overshooter** on the affected code, yet
the gate never saw it — the verdict, per-method MAPE, and damping effect were all measured on a
non-representative blend. This makes the gate faithful where the data allows.

Feasibility verified against live data: `canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl`
carries `mapped_budget_code_key`, `period_end`, `total_completed_and_stored_to_date`, `scheduled_value`,
`commitment_id` — a real per-code period history. `schedule_remaining_work` is genuinely
non-reconstructable (schedule state is not versioned).

## Decision

- **`signals.load_procore_history`** — mirrors `load_owner_history` for the mapped procore line items.
- **`backtest_strong`** — `_procore_pct_asof` (per-commitment latest row with `period_end <= T`, summed
  completed / summed scheduled, capped at 1.0); `_reconstruct` gains `procore_rows` →
  `procore_pct_to_t`; `_predict` gains `procore_progress_eac` (= `actual_to_t / procore_pct_to_t`).
  **`METHODS` (the calibration set) is deliberately UNCHANGED** — adding a method there would shift
  production `select_final` weights. (Comment added.)
- **`reconciled_backtest`** — scores the production blend over `_RECONCILED_METHODS = METHODS +
  ("procore_progress_eac",)`; real procore reliability (medium iff pct ≥ 0.50); threads `procore_history`;
  adds a `method_coverage` block (reconstructed 5 / omitted `schedule_remaining_work_eac` + reason /
  shadow-excluded `timeseries_eac` / counts) and `per_method_asof_mape` (each method's standalone as-of
  accuracy, incl. procore — diagnostic; the verdict stays on the blend).
- **`generate`** loads + passes `procore_history`. **`forecast_accuracy_gate`** surfaces `method_coverage`
  in the report so the verdict is read with its coverage in view.

## Validation

- CFR suite **649 passed** (+8). **No production forecast change** (only the backtest/gate are enriched;
  calibration `METHODS` unchanged) ⇒ all forecast value-goldens + the live cost-basis golden hold;
  determinism holds (period-bounded aggregation is deterministic). New tests: `load_procore_history`
  group/sort + missing-file; `_procore_pct_asof` per-commitment-latest + cap + empty; reconstructed
  coverage 5/6 with schedule disclosed; procore reconstructed when history present; deterministic.
- ruff/mypy: zero new issues (the lone `signals` B007 + 2 `backtest_strong` union-attr are pre-existing
  baseline, in untouched code).
- Live confirm: `docs/evidence/forecast-backtest-procore-fidelity/<stamp>/` — gate numbers 4-method vs
  5-method, procore standalone MAPE, coverage disclosure.

## NOT in this PR

No change to production `select_final` / estimators / `INDEPENDENT_METHODS` / forecast outputs / calibration.
No schema/`hb_assistant` change; no new dependency; no live write. `schedule_remaining_work` stays
omitted (no history) but is now **disclosed**. The `_RELIABILITY_DAMPING` flip remains a later
evidence-gated PR — now decidable on a faithful 5-method blend.

## Lesson (continuation of ADR 293)

The gate is only as trustworthy as its method coverage. Reconstructing the dominant omitted method —
and disclosing the one that genuinely can't be — turns the gate from a 4-method proxy into a faithful
mirror of the production blend, so future lever decisions can't be blindsided by an unseen method.
