# 16 · Forecast Staffing Plan

Turn the operator's explicit staffing schedule (extracted `staffing_json_package_tropical_*`) into a
deterministic forecast package and feed it to cost-frequency, monthly, and comprehensive. Staffing dollars
are **LAB-only**; the plan never hides a stale accepted cost-to-complete.

## Prerequisites

- A `staffing_json_package_tropical_*` package present under the data root (its own
  `validation_report.json` must pass; file hashes must match `audit/source_hashes.json`).
- The latest `forecast_context_package_*` (canonical budget codes + actuals) and
  `forecast_accuracy_next_package_*` (accepted recommendations) for the bridge.
- An operator mapping-override file:
  `config/forecast_staffing/tropical/staffing_budget_code_mapping.jsonl`. Seed an `accepted` row per cost
  code only where it uniquely resolves to one `.LAB`; otherwise leave it `pending` (review-only).

## Run

```bash
cd subrepos/construction-financial-review
PY="../../.venv/bin/python"; export PYTHONPATH=src

# 1. staffing plan FIRST (downstream slices discover its package)
$PY -m construction_financial_review.cli forecast-staffing-plan --project tropical

# 2. downstream consumers
$PY -m construction_financial_review.cli forecast-cost-frequency --project tropical
$PY -m construction_financial_review.cli forecast-monthly        --project tropical
$PY -m construction_financial_review.cli forecast-comprehensive  --project tropical
```

Determinism check:

```bash
$PY -m construction_financial_review.cli forecast-staffing-plan --project tropical \
    --frozen-stamp 20260101_000000 --out-root /tmp/sp_a
$PY -m construction_financial_review.cli forecast-staffing-plan --project tropical \
    --frozen-stamp 20260101_000000 --out-root /tmp/sp_b
diff -rq /tmp/sp_a /tmp/sp_b   # identical
```

## What to read

- `staffing_plan_summary_by_budget_code.jsonl` — the **bridge** per `.LAB` code: actual, accepted final +
  CTC, plan-implied final + remaining, `delta_vs_current_accepted_ctc`, `delta_vs_current_accepted_final_cost`,
  `requires_operator_acceptance`, and both monthly vectors.
- `staffing_plan_monthly_by_budget_code.jsonl` — `staffing_plan_implied_monthly_forecast` (plan dollars)
  vs `current_ctc_reconciled_monthly_forecast` (accepted CTC over the plan shape).
- `staffing_plan_mapping_by_cost_code.jsonl` / `staffing_plan_mapping_review_queue.jsonl` — numeric `.LAB`
  target, date-context family, status; ambiguous/unmapped/pending land in the review queue.
- `staffing_plan_conflicts.jsonl` — stale-CTC, material-final-change, recent-burn, cost-frequency,
  ends-before-horizon, reconciliation, unmapped, ambiguous classes.
- `project_staffing_plan_summary.json`, `audit/*` (mapping, monthly_reconciliation, actuals_floor,
  no_hidden_cap, source_hashes_before_after, safety_scan).

## Operator actions

- A material `delta_vs_current_accepted_ctc` means the accepted CTC disagrees with the plan — review the
  bridge and accept/reject. Plan-driven final-cost changes are **advisory** until an explicit acceptance
  slice applies them.
- To map a currently review-only cost code, add an `accepted` override row pointing at the unique `.LAB`
  key (never invent a key; never split LAB/LBN without explicit shares), then re-run.

## Guardrails

CostEntries/Sage actuals are truth; actual cost to date is the only floor. Source Excel, the staffing JSON
package, accepted packages, and SQLite are never mutated; no live external calls. No fabricated
`budget_code_key` mappings or split percentages. Deterministic quantitative core.
