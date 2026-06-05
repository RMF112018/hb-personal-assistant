# Phase 09 Prompt 27 — Context Budget Optimization (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V38 (unchanged) · **Repo SHA at build:** `4c2645d`
**Objective:** Optimize context packing while preserving source and warning metadata — an additive, advisory best-effort packer that recovers budget wasted by the baseline `apply_context_budget`.

## What changed

- **New** `retrieval/context_budget.py` — `optimize_context_packing` /
  `build_context_budget_optimization` / `build_context_budget_optimization_proof`
  (+ `ContextBudgetOptimizationError`). Reuses `apply_context_budget` + `load_context_budget` +
  `ContextBudget` (`policy.py`), the broker's pre-budget gather (`READER_REGISTRY`, allowlist/exclusion),
  and `_assert_no_raw`.
- **New** contract `phase_09_context_budget_optimization_contract.json` + seed; registered as
  `context_budget_optimization_contract` (12th Phase-09 contract).
- **New** CLI `second-brain retrieval context-budget build | proof`
  (`retrieval_context_budget_app`, `_RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS`).
- **New** tests `tests/test_phase_09_context_budget_optimization.py` (5 required paths + proof).
- **No migrator change, no DB writes** — read-only advisory report. Schema stays 38, contract table count
  stays 190. The authoritative `apply_context_budget` is **not modified**.

## Design (why it is safe)

- The baseline packer **breaks at the first overflowing item**: within the 24000-char budget (per-item
  excerpts capped at 1800), the cumulative sum can stop with free headroom while a small lower-priority
  item that would fit is silently dropped.
- `optimize_context_packing` uses the **same** priority order (tier → recency → confidence → source_ref)
  and `max_item_chars` truncation, but **skips an oversized item and continues** — recovering wasted
  budget. It **never exceeds** `max_context_chars`, **preserves** every kept item's review tier /
  confidence / source ref / freshness, and **surfaces every drop** as `budget_dropped:<family>` +
  `budget_dropped_tier{N}:<family>` coverage warnings (no silent source-coverage loss).
- **Additive, not a replacement** — `apply_context_budget` (consumed by `broker.py` 2×, `hybrid_broker.py`,
  asserted in `test_retrieval_policy.py`) is left untouched; broker adoption is deferred.
- **Advisory leaf**: `assembles_final_answer=false`; the builder **persists nothing** (no DB writes); no
  raw excerpt/content/source ref is emitted — only counts, percentages, family names, warnings.

## Operator DB outcome (real recovery; pristine)

`context-budget build --json` → `status=built`, **2045 candidate items**, baseline kept **408**,
optimized kept **412** → **4 source-linked items recovered** that the baseline break-at-overflow dropped,
`within_budget=true`, `metadata_preserved=true`, `read_only=true`. The build performs **no DB writes** —
`operator_db_mutated=false`, schema **38**.

## Proof (synthetic + build path)

`context-budget proof --json` → **`proof_passed=true`**: on a crafted set (N max-size tier-1 items fill
the budget, then an overflowing tier-1 item, then a tiny tier-2 item the baseline never reaches), the
optimizer recovers **≥1 item** over the baseline, `within_budget=true`, `metadata_preserved=true`,
`every_drop_has_warning=true`, `priority_preserved=true`, `authoritative_packer_unchanged=true`,
`build_path_no_db_writes=true`, `no_raw_emitted=true`, `assembles_final_answer=false`.

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success — 295 source files |
| `pytest -m "not live and not integration and not manual"` | 3202 passed, 0 failed |
| `construction-agent validate --json` | 4/4 (schema 38) |
| `data-quality table-inventory --json` | schema 38; contract 190; 0 unmapped live |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true |
| `second-brain data-quality phase-08b-gates --json` | **exit 1 — PRE-EXISTING / ENVIRONMENTAL (not this change)** ¹ |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain retrieval context-budget build --json` | exit 0 — 2045 candidates, 408→412 (+4), read-only, no writes |
| `second-brain retrieval context-budget proof --json` | exit 0 — proof_passed=true |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass (in the full suite) |

¹ **`phase-08b-gates` is a pre-existing/environmental failure, not caused by this prompt** (no automation
code touched). It is an `AssertionError` (`assert failed_count >= 1`) in
`automation_executor.build_automation_execution_proof` (`automation_executor.py:1485`) that **reproduces
on a pristine checkout of clean HEAD `6c43844`** in an isolated git worktree (verified in Prompt 26) —
operator Application-Support automation-state drift; the proof is not fully temp-isolated. The full pytest
suite passes (fixtures redirect `PathPolicy` to a temp root).

## Concurrency note

A parallel agent's uncommitted **"Daily Brief Approved Source Population"** changes remain in the working
tree (`daily_brief/output.py`, `research/store.py`, daily-brief tests, `docs/architecture/68`,
`145-…-daily-brief-…`). This commit stages **only** the isolated context-budget files; the other agent's
changes were left untouched (not staged, not restored). Architecture record uses **147** (145 = the
daily-brief prompt, 146 = project-benchmark).

## Deferred

Adopting `optimize_context_packing` into the authoritative broker / hybrid context budget (would change
`apply_context_budget` consumers + their tests); executing/scoring the eval set against the index
(`eval_runs`); wiring semantic context into the default `synthesize_answer` (A04).
