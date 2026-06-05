# Phase 09 Prompt 31 — Memory Consolidation Preview (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V39 (live; reuses the reserved consolidation tables added at V38) · **Repo SHA at build:** `3759a0a`
**Objective:** Generate review-only memory consolidation proposals (cluster exact-duplicate accepted memory items; propose keep-canonical + supersede-duplicates) for human review; never auto-delete/supersede/merge memory.

## What changed

- **New** `memory/consolidation_preview.py` — `cluster_consolidation_candidates` /
  `build_memory_consolidation_preview` / `persist_memory_consolidation_preview` /
  `build_memory_consolidation_preview_proof` (+ `MemoryConsolidationPreviewError`). Reuses
  `memory/store.write_memory_item` (proof fixtures), the statement-hashing concept from
  `memory/quality_review.py` (Prompt 30), and the `eval_set.py` persister pattern.
- **New** contract `phase_09_memory_consolidation_preview_contract.json` + seed; registered as
  `memory_consolidation_preview_contract` (17th Phase-09 contract).
- **New** CLI `second-brain memory consolidation-preview build | proof` (sub-group under `memory`;
  `memory_consolidation_preview_app`, `_MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS`).
- **New** tests `tests/test_phase_09_memory_consolidation_preview.py` (5 required paths + proof).
- **No migrator change, adds NO tables** — reuses the reserved V38
  `second_brain_memory_consolidation_candidates` + `…_review_items` tables.

## Design (why it is safe)

- **Clustering (deterministic, metadata-only)**: group accepted items by
  `(project_key, memory_type, sha256(statement_redacted))`; clusters of ≥2 → a proposal; oldest member =
  canonical keep, rest = proposed supersede. Statements + memory ids are SHA256-hashed (never raw).
- **Review-only — never mutates memory**: `makes_determination=false`, `auto_deletes_or_supersedes=false`,
  `review_only_proposals=true`. `long_term_memory_items` is left **byte-for-byte unchanged**; proposals
  persist (on `emit_receipt`) to the two consolidation tables (one candidate per cluster + one review item
  per member with `advisory_only=1`, `review_status='pending_review'`, `review_tier='mandatory_review'`).
- **Read-only, fail-closed, no raw**: `emit_receipt=False` persists nothing; reads accepted items via
  `mode=ro` SQL; only SHA256 hashes + counts + review vocabulary are emitted.

## Operator DB outcome (pristine)

`consolidation-preview build --json` → `status=empty`, **0 accepted items**, 0 clusters, read-only. The
operator DB has no accepted `long_term_memory_items` → no duplicate clusters → honestly empty. Direct
check: `second_brain_memory_consolidation_candidates` = **0 rows**, `…_review_items` = **0 rows**, schema
**39** — operator DB unmutated by this change.

## Proof (temp DB)

`consolidation-preview proof --json` → **`proof_passed=true`**: seeds two accepted items with the same
statement (a duplicate cluster) + one unique singleton; the duplicate pair yields **one** consolidation
proposal (a canonical keep + a supersede member); the candidate + 2 review-item rows are guard-clean with
**`advisory_only=1`**; **`long_term_memory_items` is unchanged** (same row count + same
`memory_id:review_status` fingerprint — no auto-delete/supersede); the singleton is not proposed;
`makes_determination=false`; read-only default persists nothing; no raw statement emitted.

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | **2 errors — both PRE-EXISTING in `review_burden_mart.py` (concurrent commit `3759a0a`); my module is CLEAN** ¹ |
| `pytest -m "not live and not integration and not manual"` | **3234 passed / 8 failed — all 8 PRE-EXISTING from `3759a0a`** ² |
| `construction-agent validate --json` | 4/4 (schema 39) |
| `data-quality table-inventory --json` | schema 39; contract 190; **3 unmapped — all the concurrent review_burden tables** ² |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true |
| `second-brain data-quality phase-08b-gates --json` | exit 1 — pre-existing/environmental (not this change) |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain memory consolidation-preview build --json` | exit 0 — empty (0 accepted items), read-only, no persist |
| `second-brain memory consolidation-preview proof --json` | exit 0 — proof_passed=true |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass |

¹ ² **The 2 mypy errors, 8 pytest failures, and 3 unmapped tables are ALL pre-existing regressions from the
concurrent review_burden Phase-09 commit `3759a0a`**, which migrated the schema to V39 and added
`second_brain_review_burden_runs` / `_clusters` / `_policy_evals` **without classifying them in the
lifecycle contract** (and with 2 type errors in `review_burden_mart.py`). The 8 failing tests are
`test_v{29,30,31,32,33,34,35,37}_table_classified_in_lifecycle_contract`, which assert
`in_db_not_in_contract == []`. **None of these are caused by this change** — Prompt 31 adds no tables,
touches no classification contract, and the consolidation tables it reuses are already classified; its 7
new tests all pass and `mypy` reports its module clean. These should be fixed by the review_burden owner.

## Concurrency note

Built on a heavily concurrent working tree. Per operator decision ("hold until they commit"), Prompt 31 was
held until the shared-infrastructure conflict (the review_burden agent's uncommitted V39 `migrator.py` +
`contracts.py`) was committed (`3759a0a`), then built on the clean committed base. This commit stages **only**
the isolated consolidation-preview files; the phase-07b-calendar agent's uncommitted work
(calendar/store/repositories) was left untouched.

## Deferred

Applying an approved consolidation proposal (operator review → supersede) — a later prompt; near-duplicate
(non-exact) clustering via embeddings; wiring proposals into a unified review queue.
