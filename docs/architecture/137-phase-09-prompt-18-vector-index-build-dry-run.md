# 137 — Phase 09 Prompt 18: Vector Index Build Dry Run

**Status:** Implementation — dry-run vector-index build (plan only); read-only, no embeddings, no vector store.
**Schema:** V38 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `64339cd`, Prompt 17 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/18-vector-index-build-dry-run.md` (+ `.json`, `vector-index-dry-run-proof.{json,md}`, `validation-outputs-prompt-18/`).
**Builds on:** records 131–136; reuses the Obsidian + reviewed-memory loaders, `build_approved_source_manifest`, `validate_embedding_candidate`, the LlamaIndex config, and `_FORBIDDEN`/`_assert_no_raw`.

---

## 1. Purpose

The dry-run vector-index build produces a metadata-only plan over the approved manifest's loader nodes —
what *would* be embedded and indexed — computing no embeddings and writing no vector store. The approved
manifest is the only input, and the build rejects any node lacking review tier / confidence / source
ref / freshness / no-raw proof. The apply path is Prompt 19.

## 2. Design

### Compose the prior layers; add nothing raw
The build is a thin composition: authorization = `build_approved_source_manifest`; node sources = the
two loaders (Obsidian apply-manifest + accepted memory), which already enforce approved + source-linked
+ guard-clean; the per-node rule = `_apply_build_rule` (the four named required fields +
`validate_embedding_candidate` as the no-raw proof). It computes counts, a planned chunk estimate
(`ceil(len(text)/chunk_size)`), and deterministic `config_hash` / `index_plan_hash`. No new guard logic
is forked.

### Dry-run = plan-only; vectors never in SQLite
The dry-run opens the DB `mode=ro` and persists nothing — it returns a plan with `status='dry_run'`,
`vectors_persisted_to_sqlite=false`, and `ready_to_apply` (= SDK present AND nodes>0). The V38
`vector_index_runs` table is exercised only by `persist_dry_run_record` (a single guard-clean
`status='dry_run'` row) in the proof/tests — never against the operator DB. `vector_index_items` is left
for the apply build (Prompt 19). `--apply` is fail-closed (`apply_not_enabled`) this prompt.

### Self-contained proof
`build_vector_index_dry_run_proof` builds a controlled proof DB (apply-Obsidian fixture + accepted
memory), asserts ≥1 indexable node, exercises the build rule against six planted-unsafe nodes, and
persists + re-reads a guard-clean dry-run record — covering the manifest-only input, the metadata
rejection rule, and the no-vectors-in-SQLite invariant in one artifact.

## 3. Verification

Live: operator `llamaindex build` → `dry_run`, 0 nodes (honest empty); `build --apply` → exit 3
(deferred); `build-proof` → `proof_passed` (3 nodes, 6 unsafe rejected, guard-clean dry-run record).
Full matrix: compileall/ruff clean, mypy 287 files, pytest **3127 passed** (3119 + 8 new),
`construction-agent validate` 4/4 V38, table-inventory 190 / 0 unmapped, 08A/08B/MCP gates +
no-raw/no-writeback proofs pass. Operator DB pristine (schema 38; vector-index tables 0 rows).
`phase-08c-gates` skipped (mutating ledger).

## 4. Guardrails & stop conditions

Read-only, plan-only (no embeddings / no vector store / no operator-DB writes); approved manifest is the
only input; build rule rejects nodes lacking review tier / confidence / source ref / freshness / no-raw
proof; vectors never in SQLite; metadata-only; apply deferred + fail-closed. No stop condition triggered.
