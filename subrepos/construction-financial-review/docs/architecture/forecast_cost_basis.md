# Forecast Cost-Basis (BudgetDetails Projected-Cost Deterministic Basis)

`forecast_cost_basis` is a deterministic, shared decision layer that selects, per canonical
`budget_code_key`, which cost basis governs the selected final cost and cost-to-complete:

1. accepted **operator controls** (highest priority),
2. **dormant / closed / recent-zero-run suppression**,
3. **zero-remaining suppression** (committed = 0 and no affirmative remaining evidence),
4. the **BudgetDetails projected-cost basis** (evidence-based, *never* a hidden probability cap), or
5. the existing **model basis** (fall back).

> BudgetDetails projected cost is disclosed as a **deterministic, evidence-based selected basis**, not a
> cap. It is allowed to **raise** a proven under-forecast; it is **never** used to lower a model-supported
> overrun to ERP, and it is never applied as a probability cap (`upper_cap_applied` stays `False`).

## Why

The model produced remaining forecasts directly refuted by BudgetDetails projected-cost evidence. The
canonical case `1000.15-01-426.MAT`: the `commitment_exposure_eac` estimator computed `etc = 0.00`
(`max(committed, actual)`), collapsing an open uninvoiced commitment into actuals, while
`erp_projected_reference` was tagged *"REFERENCE ONLY; never weighted, never a cap or fallback floor."*
Result: integrated final `29,615.78` / CTC `1,837.28`, against BudgetDetails:

```
projected_costs = committed_costs + erp_direct_costs + pending_cost_changes
52,778.50       = 25,000.00       + 27,778.50        + 0.00
```

`committed_costs = 25,000.00` with `commitment_invoiced = 0.00` is **open remaining exposure**, not
already-spent cost. Corrected: final `52,778.50`, CTC `25,000.00`, monthly sums to `25,000.00`.

## Module (`forecast_cost_basis/`)

- `classify.py` — `classify_budgetdetails_cost_basis(inp)`: pure, Decimal-exact decision.
- `apply.py` — `apply_cost_basis_decision(...)` (only budgetdetails/suppression statuses change the
  inbound dollars), `build_cost_basis_audit_row(...)`, `basis_disclosure_fields(...)`.
- `validation.py` — `validate_cost_basis_decisions(...)`: fail-closed gates.

## Statuses

`operator_controlled`, `dormant_suppressed`, `closed_suppressed`, `recent_zero_run_suppressed`,
`suppressed_no_remaining_commitment`, `budgetdetails_projected_cost_basis`, `existing_model_basis`,
`manual_review_required`.

## Decision precedence

1. **accepted value-asserting operator controls win** → `operator_controlled` (inbound values kept).
2. **dormant / closed / recent-zero-run suppression** → suppressed (final = actual, CTC = 0).
3. **idempotency**: an upstream-applied `budgetdetails_projected_cost_basis` (from the intelligence
   layer, carried via `upstream_cost_basis_status`) is **preserved** — not reclassified just because the
   inbound final now equals projected.
4. **committed > 0**:
   - formula present but **not** reconciling → `manual_review_required` (never projected basis).
   - `projected_costs < actual` → actuals-floor disclosure (`floor_applied`), inbound values kept.
   - `projected_costs > pre_cost_basis_model_final` (cent tol) → **`budgetdetails_projected_cost_basis`**:
     final = `projected_costs`, CTC = `max(projected_costs − actual, 0)` (asymmetric / corrective).
   - else (`model_final ≥ projected`) → `existing_model_basis`
     (`model_final_above_projected_costs_preserved_no_erp_cap`) — never caps an overrun to ERP.
5. **committed = 0**: `affirmative_remaining_evidence = any(...)` of structured booleans
   (`has_model_remaining_ctc`, `has_integrated_remaining_ctc`, `has_schedule_remaining_evidence`,
   `has_trend_or_burn_evidence`, `has_recent_actual_activity`, `has_staffing_remaining_evidence`,
   `has_positive_operator_monthly_shape`, `has_value_asserting_operator_control`). Evidence present →
   `existing_model_basis` (`committed_zero_but_model_remaining_evidence_preserved`); else →
   `suppressed_no_remaining_commitment` (CTC = 0, final = actual; primarily an audit disclosure since the
   model already has no remaining).
6. fall back → `existing_model_basis`.

The asymmetric guard compares against `pre_cost_basis_model_final` (the **original** model output, not an
already-raised inbound value) so re-application across layers is idempotent.

## Pipeline integration

- **`forecast_intelligence`** (`generate_forecast_intelligence_package.py`): after `select_final` +
  dormancy, applies/discloses the decision so `forecast_recommendations_by_budget_code.jsonl` is not left
  materially wrong, emitting `cost_basis_status`, `pre_cost_basis_model_final`, `pre_cost_basis_model_ctc`
  (worst-credible lifted to stay monotonic). Operator model controls are unknown here; comprehensive wins.
- **`forecast_comprehensive/intelligence_consumer.py`**: authoritative re-application **after** operator
  controls + dormancy, **before** the integrated CTC is returned. Drives `integrated_*` outputs.
- **`forecast_comprehensive/monthly_consumer.py`**: unchanged — it reallocates and reconciles to whatever
  corrected `integrated_ctc` it receives.
- **`forecast_comprehensive/probability_consumer.py`**: anchors the accepted distribution **up** to the
  selected final for budgetdetails-basis codes (floored at actuals, never capped), disclosed as a
  deterministic basis, not an operator cap.

## Audit & validation

- `audit/forecast_cost_basis_decision_audit.json` (comprehensive + an intelligence-layer equivalent):
  per-code formula fields, `projected_cost_formula_value/reconciles`, existing-vs-selected final/CTC,
  `cost_basis_status`, `monthly_total_after_basis`, `final_reconciliation_variance`, `reason`.
- Fail-closed gates (in `forecast_comprehensive/validation.py`, `passed = all(checks)`):
  `projected_cost_formula_reconciles` (enforced only where projected basis is **applied** — a non-applied
  mismatch surfaces as `manual_review_required`, it does not fail the package),
  `budgetdetails_projected_cost_basis_reconciles`, `monthly_reconciles_to_selected_ctc`,
  `zero_commitment_suppression_reconciles`, `actuals_floor_respected`, `operator_controls_preserved`,
  `dormant_closed_suppression_preserved`, `survey_code_1000_15_01_426_mat_projected_cost_basis`,
  `manual_monthly_1000_15_16_110_sub_preserved`.

## Live disposition (Tropical, 2026-June)

127 codes: 15 `budgetdetails_projected_cost_basis` (incl. the survey code), 36 `operator_controlled`,
4 `closed_suppressed` + 10 `dormant_suppressed` + 7 `recent_zero_run_suppressed`, 55 `existing_model_basis`.
The 21 codes where `model_final > projected` are **preserved** (overruns not capped to ERP); the only
`projected < actual` code (`1000.15-16-110.SUB`) is operator-controlled (manual_monthly), so the basis
never touches it.
