# 152 — Phase 09 Prompt 31: Memory Consolidation Preview

**Status:** Implementation — review-only memory consolidation proposals; never auto-delete/supersede; fail-closed, metadata-only, no determination.
**Schema:** V39 (live; reuses the reserved `second_brain_memory_consolidation_candidates` + `…_review_items` tables added at V38). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `3759a0a`, the concurrent review-burden V39 commit).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/31-memory-consolidation-preview.md` (+ `.json`, `memory-consolidation-preview-proof.{json,md}`, `validation-outputs-prompt-31/`).
**Builds on:** records 134–150; reuses `memory/store.py` (`write_memory_item`), the statement-hashing concept from `memory/quality_review.py` (Prompt 30, record 150), the `eval_set.py` persister pattern, and `_assert_no_raw`.

---

## 1. Purpose

Generate **review-only consolidation proposals** over the **accepted** long-term memory corpus: cluster
exact-duplicate accepted memory items and propose keeping one canonical member while superseding the
redundant duplicates — **as proposals for human review only**. It **never auto-deletes, auto-supersedes,
or auto-merges** any memory item; `long_term_memory_items` is left byte-for-byte unchanged. This
complements Prompt 30 (which flags problem *candidates*) by proposing how to consolidate redundant
*accepted* memory.

## 2. Design

### Clustering (deterministic, metadata-only)
`cluster_consolidation_candidates` groups accepted items (`review_status='accepted'`) by
`(project_key, memory_type, statement_hash)` where `statement_hash = sha256(statement_redacted)`. A
**cluster** is a group of ≥ `min_cluster_size` (2) exact-duplicate items. For each cluster the
deterministically-oldest member (sorted by `created_utc` then `memory_id`) is the canonical **keep**; the
rest are proposed **supersede**. Returns metadata-only proposal records — only SHA256 hashes of statements
and memory ids, never raw text. Singletons are never proposed.

### Review-only persistence — never mutates memory
`build_memory_consolidation_preview` reads accepted items via `mode=ro` SQL and returns a metadata-only
summary (`makes_determination=false`, `auto_deletes_or_supersedes=false`, `review_only_proposals=true`).
`emit_receipt=False` by default (persists nothing). `persist_memory_consolidation_preview` writes proposals
to the reserved V38 tables — one `second_brain_memory_consolidation_candidates` row per cluster
(candidate_id, run_id, source_memory_ref_hash, cluster_hash, confidence_class,
`review_tier='mandatory_review'`, `status='proposed'`) + one `…_review_items` row per member
(review_item_id, candidate_id, review_tier, `review_status='pending_review'`, decision_note_hash,
**`advisory_only=1`**), all 23 `CHECK(=0)` guards 0. It **never touches `long_term_memory_items`** (no
UPDATE/DELETE/supersede). **No migrator change.**

### Advisory, fail-closed, no raw
Consolidation always requires human review (proposals are `pending_review` at `mandatory_review` tier);
the surface makes no determination and applies nothing automatically. Fail-closed on missing policy / stale
schema (V38-gated, works at V39). No raw memory statement text is persisted or emitted (only hashes,
counts, review vocabulary).

## 3. Contract & seed

`phase_09_memory_consolidation_preview_contract.json` (+ `.seed.yaml`): the input review status
(`accepted`), the cluster key, `min_cluster_size`, proposal roles (`keep_canonical`/`supersede`),
proposal review tier/status, status vocab (`built`/`empty`), the two-table column allowlists,
forbidden-emitted fields (statement/memory_id/content/raw/…), and global requirements (advisory-only /
no-determination / **never-auto-delete-or-supersede** / review-only-proposals /
leave-long-term-memory-items-unchanged; preserve review tier/confidence/source refs; fail-closed).
Registered as `memory_consolidation_preview_contract` (17th Phase-09 contract).

## 4. CLI

`second-brain memory consolidation-preview build [--project] | proof` — a new sub-group under the existing
`memory` group. Unique Typer var (`memory_consolidation_preview_app`) / guardrails constant
(`_MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS`) / command names. `build` is read-only (no persist; on the
operator DB — no duplicate accepted items — honestly `empty`); `proof` runs the offline guard-clean proof.

## 5. Validation

`compileall`/`ruff` clean; `mypy src` — my new module is clean (the only 2 mypy errors are pre-existing in
`review_burden_mart.py` from the concurrent review-burden commit `3759a0a`, not this change).
`pytest -m "not live and not integration and not manual"` = **3234 passed / 8 failed** — **all 8 failures
are pre-existing** `test_v{29..37}_table_classified_in_lifecycle_contract` failures caused by the concurrent
review-burden commit `3759a0a` adding 3 tables (`second_brain_review_burden_runs`/`_clusters`/`_policy_evals`)
without classifying them in the lifecycle contract (the 3 `in_db_not_in_contract` entries). **None are from
this change** — it adds no tables, touches no classification contract, and its 7 new tests all pass. The
proof passes (seeds two accepted items
with the same statement + one unique singleton; the duplicate pair yields one consolidation proposal with a
canonical keep + a supersede member; the candidate + review-item rows are guard-clean with `advisory_only=1`;
**`long_term_memory_items` is unchanged** — same row count + same `memory_id:review_status` fingerprint;
the singleton is not proposed; no raw statement emitted; read-only default persists nothing). Operator DB
unmutated (read-only build; schema 39; table-inventory contract 190 / 3 unmapped — the 3 unmapped tables
are the concurrent review-burden commit's, not this change). `phase-08b-gates` is a **pre-existing/
environmental** failure (reproduces at clean HEAD, unrelated to this change). Full matrix in the evidence
bundle.

## 6. Deferred

Applying an approved consolidation proposal (operator review → supersede) — a later prompt / the existing
review surfaces; near-duplicate (non-exact) clustering via embeddings; wiring the proposals into a unified
review queue. The `second_brain_agent_performance_feedback_runs` table is reserved for a later prompt.

## 7. Concurrency note

Built on top of a heavily concurrent working tree: the review-burden Phase-09 prompt committed `3759a0a`
(V39 schema + `review_burden_*` tables + `review_burden_policy_contract`), and a phase-07b-calendar agent
has uncommitted work (calendar/store/repositories). Per operator decision, Prompt 31 was held until the
shared-infrastructure conflict (uncommitted V39 migrator + `contracts.py`) was committed, then built on the
clean committed base; this commit stages only the isolated consolidation-preview files.
