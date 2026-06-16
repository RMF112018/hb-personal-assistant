# Forecast Model Controls

`forecast_model_controls` is the operator-driven, accepted, auditable **per-code forecast model control**
layer. Each control is one human decision that configures the forecast model for a single canonical
`budget_code_key`. It is the value/model-configuration counterpart to `forecast_controls` (which is
timing/stop-date oriented).

> **Forecast Model Controls** are accepted, auditable per-code instructions that may control forecast
> **window**, **model shape**, **value constraints**, **manual totals**, **manual monthly values**, and
> **probability/plausibility assessment**. Final-value pinning is *one subsection* of this contract.

## Capabilities (per accepted control)

1. **Forecast window** — `forecast_start_policy` (`current_month_start` (default) / `explicit_date` /
   `schedule_activity_start` / `earliest_remaining_start`) and `forecast_end_policy`
   (`latest_project_schedule_date` (default) / `explicit_date` / `schedule_activity_finish` /
   `latest_schedule_finish` / `existing_forecast_horizon`). End resolution order: explicit date →
   code-mapped schedule date (only for code-specific end policies) → project schedule final date →
   existing-horizon fallback (only when the **entire** schedule dataset is missing/unparseable). A code
   being unmapped to schedule activities never degrades the window. `schedule_end_basis` /
   `schedule_start_basis` record which rule fired.
2. **Value constraint** — `value_constraint_policy` (`none` (default) / `equal_to_reference` /
   `not_to_exceed_reference` / `not_less_than_reference` / `explicit_final_value` /
   `explicit_remaining_value`) against a `reference_source`. A `not_to_exceed` that binds lowers the model
   result **only when accepted** and is disclosed as an operator constraint (`constraint_applied=true`) —
   never a silent cap.
3. **Model type / monthly shape** — `model_type` (`existing_model` (default) / `linear` /
   `linear_ascending` / `linear_descending` / `front_loaded_s_curve` / `back_loaded_s_curve` /
   `bell_curve` / `manual_total` / `manual_monthly`; alias `belle` → `bell_curve`). Shapes are
   deterministic normalized month→weight vectors; `existing_model` defers to the blended model.
4. **Manual values** — `manual_total` requires one of `manual_final_cost` / `manual_remaining_cost`
   (distributed by `manual_total_distribution_policy`); `manual_monthly` requires `manual_monthly_values`
   (`{YYYY-MM: amount}`), validated for valid months, in-window membership, decimal money, and
   reconciliation to any concurrent value constraint.

## Reference value sources

`explicit_user_amount`, `original_budget`, `revised_budget`, `projected_budget` (alias of
`projected_costs`), `projected_cost`, `committed_cost`, `accepted_intelligence_final`
(`recommended_final_cost`), `prior_comprehensive_integrated_final` (`integrated_recommended_final_cost`,
**prior package only — never the current run**). `projected_budget` aliases `projected_costs`; a distinct
literal `projected_budget` that disagrees emits ambiguity and fails closed.

## Precedence (per controlled code)

1. canonical mapping → 2. actuals floor → 3. forecast window → 4. value constraint → 5. model type /
shape → 6. generate monthly values → 7. apply accepted cap/equality → 8. validate. Accepted manual monthly
values are the highest-priority monthly shape; accepted explicit final/remaining control total dollars;
equality pins the total; a binding not_to_exceed constrains (disclosed); window controls bound the active
months; `existing_model` applies only where no override exists.

## Invariants (fail closed)

- Only **accepted** controls apply; pending → review queue, rejected → audit only. Flags that gate
  downstream integration are computed over **accepted** controls only, so a dormant pending control can
  never change or break downstream forecasts.
- CostEntries/Sage actuals are the **only** hard floor and are never reduced; a controlled final below
  actuals → floor conflict, not applied, integration fails closed.
- No hidden caps. Two accepted controls that disagree for one code → fail closed (no latest-wins).
- Deterministic under a frozen stamp (double-build SHA-256), source hashes unchanged, no SQLite mutation,
  no external calls, safety scan clean.

## Probability is degraded, not fatal

When a control changes the deterministic final value:
- a **prior accepted probability row** exists → the comprehensive consumer anchors `integrated_p50` to the
  controlled final, recenters the accepted spread, floors quantiles at actuals, enforces monotonicity
  (`probability_status = accepted_probability_anchor`);
- **no prior row** → a deterministic, evidence-scored **provisional plausibility assessment** is emitted
  (`provisional_manual_value_assessment`) — numeric probability fields are null (no pseudo-probabilities);
  the classification (`supported` / `plausible` / `aggressive` / `conservative` / `weakly_supported` /
  `unsupported` / `insufficient_evidence`), `evidence_support_score`, `confidence`, and `data_gaps` are
  required;
- **evidence too thin** → `probability_unavailable_insufficient_evidence` (degraded), and the deterministic
  run still completes.
The probability gate fails closed only on internal inconsistency (anchor failed with a prior row present;
no prior row and no provisional assessment; missing status; accepted lineage claimed without an accepted
source row; non-monotonic quantiles under an accepted anchor) — never merely because a prior row is absent.

## Module layout

`control_schema.py` (vocabulary + canonical field order + normalization), `load_controls.py`
(fail-closed parse + conditional required fields + override path), `mapping.py` (reuses
`forecast_controls.mapping`), `target_sources.py` (reference resolution + alias/ambiguity/circular guards),
`window_resolver.py` (per-code window), `model_shapes.py` (deterministic shape vectors), `apply.py`
(composition + precedence + manual validation + duplicate-conflict), `integration.py` (`prepare` + gates,
override-threaded), `probability_assessment.py` (provisional plausibility), `validation.py` (package
gates), `generate_forecast_model_controls_package.py` (standalone package).

Reused: `forecast_monthly/calendar.py` (window/calendar), `forecast_monthly/monthly_reconcile._allocate`
(cent-exact allocation), `common.money`/`io`/`hashing`/`safety`/`validation`, `schedule_analysis`
canonical index.

## Config + control file

`config/projects/tropical.json` → `"forecast_model_controls"` block (enabled, control_file, gate toggles,
defaults, `probability_control_policy="anchor_when_available_else_provisional_assessment"`,
`fail_on_missing_prior_probability_row=false`, `allow_provisional_probability_assessment=true`).

The committed `config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl` ships **pending
example controls only** (dormant — never changes real outputs). Operators author accepted controls there.
A `--forecast-model-control-file <path>` override (threaded into every consumer with no silent fallback)
drives validation/fixture runs.

## CLI + outputs

```
python3 -m construction_financial_review.cli forecast-model-controls --project tropical \
    [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR] [--forecast-model-control-file PATH]
```

Package `forecast_model_controls_package_tropical_<stamp>/` emits `model_controls_by_budget_code.jsonl`,
`model_control_applications_by_budget_code.jsonl`, `model_control_resolved_targets_by_budget_code.jsonl`,
`model_control_monthly_preview_by_budget_code.jsonl`,
`model_control_probability_assessment_by_budget_code.jsonl`, `model_control_review_queue.jsonl`,
`model_control_conflicts.jsonl`, `model_control_warnings.jsonl`,
`project_forecast_model_controls_summary.json`, plus `audit/` (control mapping, target-source resolution,
window resolution, actuals floor, no-hidden-cap, model shape, monthly reconciliation, probability-anchor
policy, combined-CSV target reconciliation, source hashes, safety) and `manifest.json` /
`validation_report.json` / `README.md` / `SCHEMA.md` / `input_inventory.json`.

## Downstream integration

`forecast-monthly`, `forecast-comprehensive` (intelligence/monthly/probability consumers, evidence
registry, conflicts, validation), and the combined actuals+forecast CSV consume accepted model controls
(override-threaded) so the controlled final, monthly distribution, probability anchor/assessment, and
combined CSV all reconcile to the operator's controlled result, with an explicit current-month
anti-double-count boundary audit.
