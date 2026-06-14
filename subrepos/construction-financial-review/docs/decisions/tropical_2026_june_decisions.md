# Tropical 2026-June — approved decisions & deferred work

Project: Tropical World Nursery Senior Living Facility · `tropical` · `23-435-01` · `2026-June`.
Approved by Bobby Fetting on 2026-06-14.

## Canonical interpretation rules
- BudgetDetails is the master budget-code universe (127 keys); keys are never invented.
- CostEntries are accounting actual-cost truth.
- Owner pay apps are owner-recognized billing/progress evidence.
- Procore subcontractor pay apps are vendor/commitment progress evidence.
- The authoritative crosswalk governs owner/procore scope relationships.
- No fuzzy matching; no pay-app value replaces actual cost.

## Approved analysis decisions
- `budget_amount = budget_amounts.revised_budget`; `current_projected_cost = budget_amounts.projected_costs`
  (projected_budget / estimated_cost_at_completion preserved as reference only).
- Materiality gate: `|gap| ≥ $25,000` **AND** `≥ 10%` of the larger basis. Severity tiers: critical
  (≥$250k or ≥25%), high (≥$100k or ≥15%), medium (passes gate), low.
- **Floor-to-actuals increase:** when actuals exceed projected cost,
  `recommended_projected_cost = actual_cost_all_source_to_date`,
  `recommended_forecast_adjustment = actual − projected`. Absolute precedence — review flags may lower
  confidence but never suppress the floor.
- **Decrease** only when fully gated (owner substantially complete, immaterial balance-to-finish, no
  remaining Procore exposure, material proj>actual, no June/mapping/credit issues); else review_required.
- **Actuals-only holds are `medium`** unless no-exposure is proven (forecast_to_complete 0 + immaterial
  remaining + no positive Procore remaining).
- **Owner/procore comparisons use the owner-scope rollup** with sell-value-vs-cost caution. For
  one-to-many owner SOV scopes, compare only at the rollup; do **not** allocate owner summary dollars to
  child budget codes (no allocation schedule). Children inherit rollup context only.
- `10-XX-XXX` is **description-sensitive**: GENERAL REQUIREMENTS → GR row, all other 10-XX-XXX rows →
  non-GR row. Routing must be unambiguous.
- The final authoritative crosswalk covers **all 127** canonical BudgetDetails codes and **42/42**
  Procore latest WBS codes; 0 unresolved, 0 duplicate.

## Source-of-truth note (refinement #1)
The four generators were consolidated from the **validated package-internal copies** (not from
`/tmp`); their SHA-256 hashes are recorded in `examples/tropical/input_inventory.example.json` and were
confirmed byte-identical to the working copies.

## Deferred work
- **Parameterize the generators.** They currently carry hardcoded Tropical / 2026-June data-root and
  package-name paths. Until parameterized, the CLI `run-*` commands are Tropical-only and fail clearly
  for other projects.
- Extract the generators' inline helpers to import the shared `common/` library (currently the
  generators remain self-contained; `common/` is the tested library surface).
- Optional packaging install (`pip install -e ".[dev]"`); validation here runs without install via
  `PYTHONPATH=src`.
- Apply the analysis-package refinements (#2–#5 from the v2 session) to a v1 patch if a standalone v1
  refresh is ever needed (already incorporated in crosswalk v2).
