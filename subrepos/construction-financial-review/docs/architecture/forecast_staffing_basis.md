# Forecast Staffing Basis + Full-Fresh-Run Lineage Consistency

Two related capabilities: (1) an operator staffing-plan **cost basis** for mapped `.LAB` codes, and
(2) **lineage consistency** so a fresh full run consumes one consistent context package.

## 1. Operator staffing-plan cost basis (`forecast_staffing_basis/`)

`forecast_staffing_basis` selects, per mapped `.LAB` budget code, the operator-planned remaining labor
as the deterministic selected basis when the operator has approved the staffing cost-code mapping and
the staffing source is validated — turning staffing from a monthly *timing shape* / advisory evidence
into an accepted **dollar basis**.

> Asymmetric / **raise-only**: staffing may raise an under-forecasted `.LAB` code up to the
> operator-planned remaining; it **never** silently lowers a model-supported forecast — a material
> decrease requires explicit per-code operator dollar acceptance. `.LBN`/`.MAT` never receive numeric
> staffing dollars (date-context only). Disclosed as an accepted operator basis, never a cap.

### Why

The staffing package mapped all 8 `.LAB` codes (`mapped_operator_approved_lab`, validated source) and
showed plan-implied remaining `$618,727.92` vs accepted/model CTC `$545,383.52`, yet comprehensive kept
model dollars. Staffing was consumed only as a monthly timing shape (reconciled to the accepted CTC) and
as advisory evidence (`do_not_auto_apply=true`). Canonical symptom: `1000.10-01-318.LAB` stayed at CTC
`23,145.65` instead of the staffing-plan CTC `109,045.44`.

### Gate (what makes the basis "accepted")

Two acceptance layers: the **mapping** (`staffing_plan_mapping_by_cost_code.jsonl`:
`mapping_status = mapped_operator_approved_lab`, override accepted) and the per-code **dollar**
acceptance (`acceptance_status` on the summary row, "pending" by default). The basis is gated on the
**mapping** acceptance + validated source — the operator approving the LAB mapping IS acceptance of
staffing as a dollar basis for **raises**. The per-code `acceptance_status` governs **decreases** only.

`operator_staffing_plan_basis` applies when: `category == LAB` numeric target,
`mapping_status == mapped_operator_approved_lab`, `source_validation_passed`, no accepted value-asserting
model control, not suppressed, and `staffing_implied_remaining > current_model_ctc` (cent tol). Then
`selected_cost_to_complete = staffing_plan_implied_remaining_cost`,
`selected_final_cost = actual + implied_remaining` (reason
`operator_approved_lab_mapping_validated_staffing_source_raise_only`). A decrease without explicit
acceptance → `staffing_below_model_preserved` (`staffing_plan_below_model_preserved_pending_decrease_acceptance`).

### Module + precedence

- `classify.py` `classify_staffing_basis(inp)`; `apply.py` `apply_staffing_basis_decision(...)` (only
  `operator_staffing_plan_basis` changes dollars) + `build_staffing_basis_audit_row` +
  `staffing_disclosure_fields`; `validation.py` `validate_staffing_basis_decisions(...)`.
- Final integrated-dollar precedence: 1. accepted value-asserting model controls → 2. dormant/closed/
  recent-zero suppression → 3. **operator staffing-plan basis** → 4. BudgetDetails projected-cost basis
  → 5. existing model basis. Hooked in `forecast_comprehensive/intelligence_consumer.build()` after
  operator controls + dormancy, before the BudgetDetails basis (which it pre-empts via
  `staffing_basis_applied`).
- Monthly: `monthly_consumer` reallocates to the corrected `integrated_ctc`, so the monthly sum
  reconciles to the staffing CTC automatically (timing logic unchanged; row discloses
  `staffing_basis_status`). Probability anchors the accepted distribution up to the staffing-selected
  final (floored at actuals, never capped).
- Comprehensive reads the **existing** staffing package's `staffing_plan_summary_by_budget_code.jsonl`,
  `staffing_plan_mapping_by_cost_code.jsonl`, and `staffing_plan_source_inventory.json`
  (`evidence_registry.load_sources`), so the basis applies without regenerating staffing.

### Audit + gates

`audit/forecast_staffing_basis_decision_audit.json` (one row per staffing-relevant code: model vs
staffing final/CTC, deltas, status, selected final/CTC, `monthly_total_after_staffing_basis`,
`final_reconciliation_variance`, reason). Fail-closed gates:
`staffing_package_present_if_config_enabled`, `staffing_mapping_all_accepted_rows_resolved`,
`staffing_basis_reconciles`, `staffing_monthly_total_reconciles_to_selected_ctc`,
`staffing_actuals_floor_respected`, `staffing_lab_only_numeric_application`,
`staffing_does_not_apply_to_lbn_or_mat`, `model_controls_override_staffing`. The pre-existing
`operator_staffing_plan_advisory_requires_acceptance` gate is relaxed to exclude codes where the basis
is applied (those evidence items are no longer advisory-only).

### Live disposition (Tropical, 2026-June)

8 mapped staffing `.LAB` codes: 5 raise → `operator_staffing_plan_basis` (302, 311, 315, **318**, 460);
3 decrease preserved on model (310, 314, 317). `1000.10-01-318.LAB`: CTC `23,145.65 → 109,045.44`,
final `408,425.76`, monthly sum `109,045.44`.

## 2. Full-fresh-run lineage consistency (`common/lineage.py`)

Each stage previously resolved its upstream context independently (`schedule_io.discover_packages`
preferred the **configured** `forecast_context_package` — stale `...20260614_084510` — while
comprehensive used latest-glob → `...20260617_043410`), so a fresh run silently mixed stale + fresh
packages with no detection.

- **Shared resolver** `resolve_context_package(data_root, cfg, project_key, context_stamp=None,
  strict_pin=False)` + `pin_context_into_cfg(...)`: every context-consuming stage (intelligence,
  monthly, probability, staffing_plan, cost_frequency, comprehensive) resolves context uniformly
  (default latest-glob, superseding the stale configured name) and records `context_lineage`
  (`consumed_context_package/stamp`, manifest `generated_at`/`hash`, `lineage_source`) in its
  `input_inventory.json`.
- **Pinning** `--context-stamp <YYYYmmdd_HHMMSS>` (CLI) carries through `cfg` and resolves the exact
  context package; a missing pin **fails closed** (no silent fallback to latest).
- **Gate** `full_run_lineage_consistent` (`audit/forecast_run_lineage_audit.json`): compares the
  consumed context stamp across all present packages vs the comprehensive context. A genuine
  inconsistency (a package recorded a different stamp) **always** fails. Missing lineage metadata fails
  closed only under a pinned (strict) fresh run; on legacy/ad-hoc runs it is reported but the
  inconsistency check remains authoritative. Absent/feature-disabled packages are not_applicable.
- **Runner** `scripts/run_full_fresh_tropical_forecast.sh` derives the freshly generated context stamp
  after `run-context` and passes `--context-stamp` to every downstream context-consuming stage, so a
  fresh full run is reproducibly lineage-consistent.
