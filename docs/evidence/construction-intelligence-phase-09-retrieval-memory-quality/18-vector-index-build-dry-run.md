# Phase 09 Prompt 18 — Vector Index Build Dry Run

**Evidence artifact:** `phase_09_vector_index_build_dry_run` · **Companion JSON:** `18-vector-index-build-dry-run.json`
**Proof companions:** `vector-index-dry-run-proof.json` (+ `.md`).
**Classification:** Phase 09 implementation — dry-run vector-index build (plan only) over the approved manifest.
**Schema:** V38 (unchanged). **Version:** 1.3.0.
**Posture:** metadata-only, local-only, read-only, **dry-run (no embeddings, no vector store)**, fail-closed. The operator DB stays pristine.
**Builds on:** records 131–136 (V38 schema, LlamaIndex config, embedding policy, approved manifest, Obsidian + memory loaders); reuses the loaders, `build_approved_source_manifest`, `validate_embedding_candidate`, the LlamaIndex config, and `_FORBIDDEN`/`_assert_no_raw`.

---

## 1. Purpose

The dry-run vector-index build produces a **metadata-only plan** — what *would* be embedded and indexed
— over the **approved source manifest's** loader nodes, **computing no embeddings and writing no vector
store**. Per the vector-build-specific instruction, the approved manifest is the only input and the
build **rejects any source lacking review tier, confidence, source ref, freshness metadata, or no-raw
proof**. The apply path (real embeddings + vector store) is Prompt 19.

## 2. What changed

### Build module (`retrieval/vector_index.py`)
- `build_vector_index_dry_run(db_path, *, project_key)` — read-only (`mode=ro`): loads the embedding
  policy + LlamaIndex config (fail-closed); fail-closed schema check (≥38 + `vector_index_runs`);
  gathers nodes from the Obsidian + reviewed-memory loaders with `build_approved_source_manifest` as
  authorization; applies the build rule per node (`_apply_build_rule` = the four required fields +
  `validate_embedding_candidate`'s no-raw proof); computes the plan — per-family node counts,
  `planned_chunk_count`, `config_hash`, `index_plan_hash`, `sdk_available`, `ready_to_apply`,
  `no_raw_attested`, `vectors_persisted_to_sqlite: false`, manifest provenance, warnings,
  `status='dry_run'`. Persists nothing.
- `persist_dry_run_record(db_path, plan, *, policy_version)` — INSERTs one guard-clean
  `status='dry_run'` `vector_index_runs` row (no `vector_index_items` — those are the apply build).
  Proof/test only — not run against the operator DB.
- `build_vector_index_dry_run_proof(...)` — fail-closed proof combining a controlled proof DB
  (apply-Obsidian fixture + accepted memory) → plan with ≥1 indexable node, the build rule rejecting
  planted-unsafe nodes, and a guard-clean dry-run record persisted to the proof DB. Writes a guard-clean
  JSON+MD companion.

### CLI
- New `second-brain retrieval llamaindex build` (dry-run by default; `--apply` is fail-closed
  `apply_not_enabled`, deferred to Prompt 19) and `... build-proof`.

## 3. Key results (live)

- `llamaindex build` (operator DB, dry-run): **status `dry_run`**, `total_nodes=0` — the operator has 0
  approved Obsidian + 0 accepted memory, so there is nothing to plan (honest `no_approved_nodes` +
  `generated_outputs_loader_deferred` warnings); `ready_to_apply=false` (SDK absent + 0 nodes);
  `vectors_persisted_to_sqlite=false`. Exit 0.
- `llamaindex build --apply`: fail-closed `status=apply_not_enabled` (deferred to Prompt 19), exit 3.
- `llamaindex build-proof`: **`proof_passed=true`** — a controlled proof DB plans **3** indexable nodes
  (2 Obsidian + 1 memory); the build rule rejects all 6 planted-unsafe nodes (missing review-tier /
  confidence / source-ref / freshness, raw-shape text, non-embeddable family); a guard-clean
  `status='dry_run'` `vector_index_runs` row persists (item_count 3, `raw_vector_content_persisted=0`).
- Operator DB: schema **38**; `vector_index_runs`/`vector_index_items` remain **0 rows** (dry-run is
  plan-only).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**287** source files) ·
`pytest -m "not live and not integration and not manual"` → **3127 passed / 0 failed / 1 deselected**
(prior 3119 + 8 new) · `construction-agent validate` 4/4 schema **V38** · `table-inventory` 190 / 0
unmapped · `no-writeback-proof` `proof_passed=true` · `phase-08a-gates`/`phase-08b-gates` ok ·
`mcp no-raw-access`/`mcp no-writeback` `proof_passed=true` · `retrieval llamaindex build` exit 0 /
`build --apply` exit 3 / `build-proof` exit 0. `phase-08c-gates` deliberately skipped (mutating
append-only ledger — disclosed Prompts 02/05). Captures under `validation-outputs-prompt-18/`.

The 8 new tests cover: normal dry-run + guard-clean persist; missing-policy fail-closed; stale-schema
fail-closed; build-rule rejects unsafe nodes; dry-run does not mutate the DB; proof passes + is clean;
proof writes guard-clean artifacts; CLI apply-deferred + build-proof exit codes.

## 5. Guardrails & stop conditions

Dry-run is read-only (`mode=ro`) and plan-only — no embeddings, no vector store, no operator-DB writes;
the **approved manifest is the only input**; the build rule rejects any node lacking review tier /
confidence / source ref / freshness / no-raw proof; vectors are never persisted to SQLite; metadata-only
plan/evidence (no node text); apply is deferred and fail-closed. No stop condition triggered.

## 6. Deferred / owning prompts

The apply build (real embeddings + vector store + `vector_index_items`) is Prompt 19. A generated-outputs
(research packets) loader is not yet built — that manifest category is deferred from this build.
