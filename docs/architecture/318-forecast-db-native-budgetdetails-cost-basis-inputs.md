# 318 — Forecast DB-native BudgetDetails cost-basis inputs (Phase E2)

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation — Phase E2 (interstitial, between E and F)
- Related: ADR 317 (DB-native generation engine), ADR 316 (context builder), ADR 315 (source snapshot)

## Context

Phase E (ADR 317) shipped the DB-native comprehensive engine but documented a material gap: the
DB-native financial spine (v59 `forecast_budget_details`) carries no `erp_direct_costs` /
`pending_cost_changes`, so the canonical `forecast_cost_basis` formula

    projected_costs = committed_costs + erp_direct_costs + pending_cost_changes

cannot reconcile, and committed-cost codes route to `manual_review_required` instead of the asymmetric
`budgetdetails_projected_cost_basis` raise. The structured Procore table `procore_ep_budget_detail_rows`
(migrator V55/V56) carries the missing fields. Phase E2 feeds real DB-native BudgetDetails formula
inputs into the snapshot → context → comprehensive engine so the canonical decision can be evaluated —
with no persistence, no route wiring, no live-DB mutation, and no migrator/schema change.

## Decision

### Snapshot fields added (`forecast_db_native_source_snapshot.py`)

A new path-free `budgetdetails_cost_basis_inputs` section in `DbNativeSourceSnapshot.public()`, one
deterministically-selected BudgetDetails view per budget code:

```
budgetdetails_cost_basis_inputs: { present, row_count, rows: [ {
  budget_code_key, committed_costs, erp_direct_costs, pending_cost_changes, projected_costs,
  actual_cost, job_to_date_costs, erp_job_to_date_costs, forecast_to_complete,
  estimated_cost_at_completion, commitment_invoiced,
  pending_budget_changes,                      # budget-side context ONLY — never a formula input
  formula_reconciles, formula_variance, missing_formula_fields,
  candidate_view_count, selected_budget_view_id, selected_source_quality,
  selected_formula_reconciles, selection_method: "db_deterministic", selection_warnings } ] }
```

### Tables / columns read (read-only, `mode=ro`)

- `procore_ep_budget_detail_rows` — stable money columns `committed_costs`, `erp_direct_costs`,
  `projected_costs`, `actual_cost`, `job_to_date_costs`, `erp_job_to_date_costs`, `forecast_to_complete`,
  `estimated_cost_at_completion`, `pending_budget_changes`; keys `canonical_budget_code_key` /
  `wbs_flat_code`, `budget_view_id`, `source_quality`, `is_current`.
- `procore_ep_budget_detail_row_cells` — the two **dynamic** cost-basis fields `pending_cost_changes`
  and `commitment_invoiced`, sourced **only** via
  `budget_column_roles.procore_label_to_role_key(column_label)` → role, reading `value_decimal_text`.
  `pending_budget_changes` (budget-side) is **never** substituted for `pending_cost_changes`.

No `record_key`, `payload_hash`, `raw_payload`, paths, or package names are emitted (redaction-safe).

### Budget-view selection (DB-deterministic, path-free)

Candidates are `is_current=1` rows for the project mapped to the budget code. Per code, ranked by:
(1) `source_quality` rank (reuse `structured_analytics.SOURCE_QUALITY_RANK`: `live_full_payload` >
`fixture_full_payload` > `redacted_legacy_projection`), (2) `formula_reconciles` True first,
(3) formula completeness, (4) latest `payload_seen_last_utc`/`updated_utc`, (5) deterministic tiebreak
`budget_view_id` then `record_key`. Exactly one view per code; formula fields are never mixed across
views. When `candidate_view_count > 1`, emit `budgetdetails_multiple_budget_views_detected` +
`budgetdetails_selected_view_unverified`. The config-file selector
(`_configured_budget_detail_view_ids` / `config/projects/*.json`) is **not** read — the DB-native path
stays path-free.

### Missing-vs-zero and conflicts

Missing/blank/non-numeric → field unavailable; a real `"0.00"` is kept. `formula_reconciles` is True
only when committed_costs, erp_direct_costs, pending_cost_changes, projected_costs are all present and
`|projected − (committed + erp_direct + pending_cost_changes)| ≤ 0.01`. Duplicated/conflicting dynamic
cells for a role → the field is marked missing (never fabricated) + `budgetdetails_dynamic_cell_conflict`.

### Context mapping (`db_native_context_builder.py`, package-free)

Each `budget_code_context` row gains a `cost_basis_inputs` block (the formula fields + diagnostics +
`source: "db_native_budgetdetails"`). A code with no matching BudgetDetails row →
`{available: False, reason: "budgetdetails_cost_basis_inputs_unavailable"}` + a data-quality warning;
the build never fails (the financial spine still drives it). `budget_column_roles` is used only HB-side
in the snapshot; the builder remains free of `hb_assistant` imports.

### Engine behavior change (`db_native_generation_engine.py`, package-free)

When `cost_basis_inputs.available`, `_comprehensive_line` feeds the real formula fields to the unchanged
`forecast_cost_basis.classify`/`apply`, with **Procore EAC** (`estimated_cost_at_completion`) as the
pre-basis model baseline (floored to actual). So:

- Reconciling formula with `projected_costs > EAC` → `budgetdetails_projected_cost_basis` (asymmetric
  raise); final = projected, CTC = projected − actual.
- `EAC ≥ projected` → `existing_model_basis` (never cap an overrun down to ERP).
- Non-reconciling formula (e.g. `pending_cost_changes` missing) → `manual_review_required`.

Actuals remain authoritative from the v59 spine (cost-entry sum) — the Procore `actual_cost` is carried
for diagnostics only. Final ≥ actual; CTC = `max(final − actual, 0)`. When `cost_basis_inputs` is
unavailable, the engine falls back to the exact Phase E v59-spine behavior (`cost_basis_source` records
which path ran). No new formula is introduced; no owner/Procore/crosswalk influence is fabricated.

### Examples

- **Reconciled raise**: committed 600 + erp_direct 300 + pending_cost_changes 100 = projected 1000;
  EAC 850 → `budgetdetails_projected_cost_basis`, final 1000.00.
- **Non-reconciled**: pending_cost_changes missing → `formula_reconciles=False` →
  `manual_review_required` (projected number surfaced, flagged — not synthesised).

## Consequences

- The headline E317 blocker is resolved: committed-cost codes with a reconciling DB-native BudgetDetails
  formula reach `budgetdetails_projected_cost_basis`.
- DB-native path stays read-only and path-free; `find_redaction_leaks(...) == []`.
- `monthly`/`probability`/`model_controls` remain explicitly unsupported.
  `POST /api/forecast/runs/db-native` remains fail-closed (`db_native_generation_not_implemented`).
- No migrator/schema/v60/table-count change; no `hb_assistant` schema change; legacy generators untouched.

## Non-goals (deferred to Phase F+)

- Output persistence / certification / route wiring (Phase F).
- DB-native owner/Procore/crosswalk source families and the non-comprehensive generator kinds.
- Operator-certified budget-view configuration on the DB-native path.

## Guardrails

No Phase F persistence; no route wiring; no live-DB mutation; no external calls; no
package/source/context/analysis directory reads; no config/project JSON read; no package fallback; no
new formula (reuse `forecast_cost_basis`); no fabricated values for missing components. CFR
engine/context import no `hb_assistant`.
