# 101 — Phase 08C Currency, WBS, and Cost-Code Completeness (Prompt 04)

**Baseline**: Post-P03 amount normalization at `d5cb0e8` (V35, amount_facts_normalized carrying currency_code + source_field_path for parseables; 08c gates stub "pass" for currency/wbs/source/review; no snapshot population or review routing for these triggers yet).

**Objective** (per prompt): Measure currency, WBS, cost-code, line-item-type, and source-field-path completeness.
- Implement currency completeness snapshots (6 statuses per contract, project default only under full 4 evidence-backed policy conditions + marked).
- Implement WBS/cost-code completeness snapshots (5 status values, counts per required dim).
- Add project-default currency handling only when evidence-backed by policy (contract + currency_policy.seed.yaml conditions).
- Route missing/inconsistent/ambiguous to review_required_items (triggers "missing_or_inconsistent_currency", "missing_wbs_cost_code_or_line_item_type", "missing_source_field_path").
- Generate `currency-completeness-report.json` and `wbs-cost-code-coverage-report.json`.

**Tests** (explicit currency, default allowed, default blocked, inconsistent, missing wbs/cost/source) pass with correct statuses, counts, review routing, policy enforcement, no float/REAL, no raw, source preserved.

## Implementation
- New `src/hb_assistant/construction/second_brain/financial_completeness.py`:
  - Policy/ contract loaders (currency default conditions, wbs dims, review triggers/tiers).
  - `build_currency_completeness_snapshot`: aggregates from amount_facts_normalized (currency_code, source_field_path) + source; applies `_is_evidence_backed_project_default` (all 4 conditions); inserts to currency_completeness_snapshots with status/counts/project_default_applied flag; routes to review for missing/inconsistent.
  - `build_wbs_cost_code_completeness_snapshot`: queries line_items/rows + normalized for wbs/cost/line/source presence; counts; routes missing to review with correct trigger.
  - `build_source_coverage_snapshot`: per required family, field counts (amount/currency/wbs/source), coverage_status per contract.
  - `route_to_review`: inserts to review_required_items with trigger_category + review_tier + refs + guards/advisory=1.
  - `run_financial_completeness`: orchestrator.
  - `build_*_report`: run + aggregate + atomic write the two named JSON reports (per-project stats, contracts, policy notes, "default only evidence-backed", "no raw", advisory, source preserved).
- Wired in `data_quality.py`: 08c evaluate calls run_completeness; currency/wbs/source/review gates now return real stats/counts/%/statuses (not stub "pass"); build_proof includes snapshots.
- `cli/second_brain.py`: financial coverage now includes source_coverage_snapshots + completeness summary (real, not just contract stub).
- New focused test `tests/test_phase_08c_financial_completeness.py`: temp V35 DB, seeds (str amounts), 6+ cases (explicit/default-allowed/blocked/inconsistent/missing wbs/source), asserts snapshots/guards/CHECKs/review items/reports.
- Reports generated in evidence (structure from contracts, no raw, policy enforced, advisory).

All money paths reuse P03 Decimal helpers (no new float/REAL/JSON num coercion).

Source data read-only; snapshots/reports contain only counts/statuses/refs + guards/advisory=1.

## Verification
- pytest new completeness test (all cases, policy blocks default, review routed, reports generated).
- 08c-gates now report real (e.g. explicit/default/missing/inconsistent counts, wbs % per dim, source field counts, routed review).
- financial coverage --json reports real snapshots.
- no-writeback still true (new module guarded, no raw).
- Reports clean (sensitive 0, "default only when...", "source preserved", "no raw").
- Harness + seeds + builders + reports + asserts (LATEST, correct statuses per contract, policy, guards, no float).
- Stops clear (grep no float in new, default never without full evidence-backed conditions, source TEXT untouched).

Staged only required (new module, data_quality edit, cli edit, new test, 2 reports, 101-md, 00-README).

Package for title/version + contracts/seeds as spec; repo truth authoritative.

**Prompt 04 complete. 08C not closed.**