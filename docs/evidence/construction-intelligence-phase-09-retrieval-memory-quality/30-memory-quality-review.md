# Phase 09 Prompt 30 — Memory Quality Review (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V38 (unchanged) · **Repo SHA at build:** `04112c5`
**Objective:** Evaluate proposed long-term memory candidates for duplicate/stale/conflicting status against the accepted memory corpus, and flag problem candidates for human review. Advisory only — never merges, deletes, or accepts memory; makes no determination.

## What changed

- **New** `memory/quality_review.py` — `evaluate_memory_candidates` / `build_memory_quality_review` /
  `persist_memory_quality_review_run` / `build_memory_quality_review_proof`
  (+ `MemoryQualityReviewError`). Reuses `memory/store` (read candidates, `write_memory_item`),
  `memory/curator.propose_memory_candidate`, `memory/policy.classify_memory_tier` (→
  `T3_CONFLICT_DETECTED`), and the `eval_set.py` persister pattern.
- **New** contract `phase_09_memory_quality_review_contract.json` + seed; registered as
  `memory_quality_review_contract` (15th Phase-09 contract).
- **New** CLI `second-brain memory quality-review build | proof` (a sub-group under the existing `memory`
  group; `memory_quality_review_app`, `_MEMORY_QUALITY_REVIEW_GUARDRAILS`).
- **New** tests `tests/test_phase_09_memory_quality_review.py` (5 required paths + proof).
- **No migrator change** — reuses the reserved V38 `second_brain_memory_quality_review_runs` table.
  Schema stays 38, contract table count stays 190.

## Design (why it is safe)

- **Detection (deterministic, metadata-only)**: statements are SHA256-hashed (`statement_redacted`), never
  stored/emitted raw. duplicate = statement-hash matches an accepted item (or another candidate); stale =
  matches a *superseded* item; conflicting = `review_tier_reason_code == "T3_CONFLICT_DETECTED"` (the
  deterministic curator conflict code).
- **Advisory — no determination, no mutation of memory**: `makes_determination=false`,
  `merges_or_deletes_or_accepts=false`, `routes_flagged_to_review=true`. It flags for human review; it
  never decides, merges, deletes, or accepts.
- **Read-only, metadata-only**: reads candidates + accepted/superseded items via `mode=ro` SQL (zero
  writes); `emit_receipt=False` persists nothing; the receipt (one guard-clean run row) carries only
  hashes, counts, and review vocabulary — never raw statement/decision text.

## Operator DB outcome (real result; pristine)

`memory quality-review build --json` → `status=clean`, **1 candidate reviewed**, **0 flagged**. The
operator DB has one proposed memory candidate; it is clean (not duplicate/stale/conflicting). Direct
check: `second_brain_memory_quality_review_runs` = **0 rows**, schema **38** — `operator_db_mutated=false`.

## Proof (temp DB)

`memory quality-review proof --json` → **`proof_passed=true`**: seeds an accepted item, a superseded item,
and four proposed candidates (a duplicate, a stale restatement, a conflicting one, and a clean one),
`flagged_count=3` (duplicate + stale + conflicting all detected), the run row guard-clean + metadata-only,
`makes_determination=false`, `read_only_default_no_persist=true`, `no_raw_statement_emitted=true`.

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success — 298 source files |
| `pytest -m "not live and not integration and not manual"` | 3227 passed, 0 failed |
| `construction-agent validate --json` | 4/4 (schema 38) |
| `data-quality table-inventory --json` | schema 38; contract 190; 0 unmapped live |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true |
| `second-brain data-quality phase-08b-gates --json` | **exit 1 — PRE-EXISTING / ENVIRONMENTAL (not this change)** ¹ |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain memory quality-review build --json` | exit 0 — 1 candidate, status=clean, read-only, no persist |
| `second-brain memory quality-review proof --json` | exit 0 — proof_passed=true (3 flagged) |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass (in the full suite) |

¹ **`phase-08b-gates` is a pre-existing/environmental failure, not caused by this prompt** (no automation
code touched). It is an `AssertionError` (`assert failed_count >= 1`) in
`automation_executor.build_automation_execution_proof` (`automation_executor.py:1485`) that **reproduces
on a pristine checkout of clean HEAD `6c43844`** in an isolated git worktree (verified in Prompt 26) —
operator Application-Support automation-state drift; the proof is not fully temp-isolated. The full pytest
suite passes (fixtures redirect `PathPolicy` to a temp root).

## Concurrency note

A parallel **"phase-07b-calendar-index-apply-robustness"** agent has uncommitted work in the tree
(`calendar/event_indexer.py`, `store/repositories.py`, calendar tests, arch 21/148). This commit stages
**only** the isolated memory-quality-review files; the other agent's work was left untouched. Architecture
record uses **150** (148 is collided between my committed `148-phase-09-prompt-28` and the concurrent
`148-phase-07b-…`; 149 is mine).

## Deferred

Memory **consolidation** (clustering duplicates into merge proposals via the reserved
`second_brain_memory_consolidation_candidates` / `_review_items` tables) — a later prompt; executing the
operator review decision on flagged candidates (the existing `memory review` surface); wiring
`long_term_memory_quality_signals` (freshness/conflict) into the evaluation.
