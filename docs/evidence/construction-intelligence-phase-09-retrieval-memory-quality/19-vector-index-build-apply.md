# Phase 09 — Prompt 19: Vector Index Build Apply (Evidence)

- **Package version:** 1.4.0-phase-09
- **Repo SHA at build:** `b0430c959f1955ccdb0188d1b1cce62065542364`
- **Schema:** V38 (unchanged — `vector_index_runs` + `vector_index_items` already existed; contract table count stays 190)

## Objective

Implement the policy-gated **apply** build: embed the approved nodes via LlamaIndex, write the vector
store on the local filesystem (**never SQLite**), and persist metadata-only receipts (one
`status='applied'` `vector_index_runs` row + one `vector_index_items` row per node). Fail closed when the
optional SDK is absent, there are no indexable nodes, or policy/schema is not ready.

## What changed

- **`retrieval/vector_index.py`** — extracted `_build_plan` (shared by dry-run + apply); added
  `_ITEMS_TABLE`, the apply contract/seed loaders, an injectable `VectorStoreWriter` port, the default
  `_llamaindex_vector_writer` (LlamaIndex `VectorStoreIndex` + `SimpleVectorStore` +
  `HuggingFaceEmbedding`), `build_vector_index_apply`, `persist_apply_record`, the offline
  `_mock_vector_writer`, and `build_vector_index_apply_proof`.
- **`contracts.py`** — registered `vector_index_apply_contract` in `PHASE_09_CONTRACT_FILES`.
- **`cli/second_brain.py`** — `build --apply` now embeds + persists receipts (fail-closed → exit 3 on
  `apply_blocked`/`not_ready`); added `build-apply-proof`.
- **Contract/seed** — `phase_09_vector_index_apply_contract.json` + `phase_09_vector_index_apply.seed.yaml`
  (persisted-column allowlist, forbidden persisted fields, allowed statuses, blocker reasons,
  external-vector-store requirement).
- **Dependency** — installed the optional `.[retrieval-local]` extra so the SDK is present
  (`pyproject.toml` unchanged; extras declared in Prompt 13).

## Apply build proof — `build-apply-proof` (exit 0, proof_passed=true)

| check | result |
|---|---|
| applied item count | 3 |
| embedding dim | 384 |
| vectors written outside SQLite | true |
| vectors persisted to SQLite | **false** |
| run record guard-clean (23 guards) | true |
| item records guard-clean (23 guards) | true |
| no forbidden persisted columns | true |
| blocked when no indexable nodes | true |
| build-rule cases (safe + 6 planted-unsafe) | all passed |

## Real HuggingFace embed smoke (`BAAI/bge-small-en-v1.5`)

A genuine local embed (default writer, no mock) produced `status='applied'`, 3 items, dim 384, with the
LlamaIndex `SimpleVectorStore` persisted to disk as `default__vector_store.json`, `docstore.json`,
`graph_store.json`, `image__vector_store.json`, `index_store.json` — **outside SQLite** — and 3
metadata-only item rows in SQLite. Captured at
`validation-outputs-prompt-19/real-huggingface-embed-smoke.json`. Automated equivalent:
`tests/test_phase_09_vector_index_apply.py::test_apply_real_huggingface_embed_smoke` (marked
`integration`, excluded from the default-safe subset).

## Operator DB outcome

`build --apply` against the operator DB returns `apply_blocked: no_indexable_nodes` (exit 3) — the
operator DB has zero approved sources, so apply honestly blocks and **persists nothing**. Schema stays
38; `vector_index_runs` and `vector_index_items` remain **0 rows**. Operator DB data is unmutated.

## Validation matrix

- `python -m compileall src tests` → exit 0
- `ruff check .` → All checks passed!
- `mypy src` → Success: no issues found in 287 source files
- `pytest -m "not live and not integration and not manual"` → **3135 passed, 0 failed, 2 deselected**
- `construction-agent validate --json` → exit 0 (schema 38)
- `construction-agent data-quality table-inventory --json` → exit 0 (contract_table_count=190, 0 unmapped)
- `construction-agent data-quality no-writeback-proof --json` → exit 0
- `second-brain data-quality phase-08a-gates --json` → exit 0
- `second-brain data-quality phase-08b-gates --json` → exit 0
- `second-brain data-quality phase-08c-gates` → **SKIPPED** (mutates operator DB: ~1,299 ledger rows/call)
- `second-brain data-quality phase-08d-gates --json` → exit 0
- `second-brain mcp no-raw-access --json` → exit 0
- `second-brain mcp no-writeback --json` → exit 0
- `second-brain retrieval llamaindex status --json` → exit 0 (sdk available, ready_to_index)
- `second-brain retrieval llamaindex build --json` → exit 0 (dry-run)
- `second-brain retrieval llamaindex build --apply --json` → exit 3 (`apply_blocked: no_indexable_nodes`)
- `second-brain retrieval llamaindex build-apply-proof --json` → exit 0 (`proof_passed=true`)
- post-CLI guard re-run (`test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof`) → pass

> The prompt's exact-command list used stale MCP paths (`mcp data-quality …`); the real commands are
> `second-brain data-quality phase-08d-gates`, `second-brain mcp no-raw-access`, `second-brain mcp
> no-writeback` — all run, all exit 0.

## Deferred

- `generated_outputs` (research-packet) loader still absent — apply covers Obsidian + reviewed memory
  only (warning `generated_outputs_loader_deferred`).
- Hybrid query / semantic retrieval read path, eval sets, benchmarks, memory-quality review — later
  Phase 09 prompts. Prompt 07 (G-05 Memory Runtime & Review preflight) remains unrun.

## Incidental fix

`tests/test_phase_09_schema_status.py::test_helper_does_not_mutate_db` dropped its flaky file-size
(`st_size`) assertion, keeping the authoritative `schema_migrations` row-count invariant (WAL
checkpointing resizes the file without any row change; documented project guidance prefers row counts).
The same latent pattern in three sibling Phase 09 tests was left untouched (it did not flake; surgical
scope).
