# Phase 09 — Prompt 20: Hybrid Retrieval Broker (Evidence)

- **Package version:** 1.4.0-phase-09
- **Repo SHA at build:** `3d9e34216a9d94c8889e08f61387cb31e48b50e2`
- **Schema:** V38 (unchanged — `hybrid_query_runs` + `hybrid_query_results` already existed; contract table count stays 190)

## Objective

Combine **deterministic** retrieval (the authoritative `RetrievalBroker` over the allowlisted families)
with an **advisory semantic** path (query the applied vector index), merged into one source-linked,
guard-clean context — **while preserving source-of-truth discipline**: semantic results are advisory
suggestions only and the broker never assembles a final answer (that stays in the Research Packet /
Evaluation layers).

## What changed

- **`retrieval/hybrid_broker.py`** (new) — `build_hybrid_retrieval` (deterministic + advisory semantic
  merge, re-budgeted), `build_hybrid_status`, the semantic read path (`_semantic_query` loads the applied
  `SimpleVectorStore`, embeds the query, source-links each match to a `vector_index_items` receipt and
  re-validates with the no-raw guardrail), `persist_hybrid_query_record` (metadata-only receipts), and
  `build_hybrid_retrieval_proof`. Injectable `embed_model` (default HuggingFace `bge-small`; proofs/tests
  inject `MockEmbedding`).
- **`contracts.py`** — registered `hybrid_retrieval_contract` in `PHASE_09_CONTRACT_FILES`.
- **`cli/second_brain.py`** — new `retrieval hybrid` group: `status`, `search`, `proof`.
- **Contract/seed** — `phase_09_hybrid_retrieval_contract.json` + `phase_09_hybrid_retrieval.seed.yaml`
  (modes, advisory posture, score buckets, run/result column allowlists, forbidden persisted fields,
  skip/blocker reasons).
- **No migrator change**, **no synthesis rewiring** (hybrid broker is wiring-ready; A02/A04 adoption deferred).

## Source-of-truth discipline

| property | value |
|---|---|
| deterministic authoritative | true |
| semantic advisory only | true |
| `assembles_final_answer` | **false** |
| `semantic_retrieval_bypassed_policy` | **0** |
| preserved | review tier, confidence class, hashed source refs, freshness, coverage warnings |
| MCP exposure | none (vector/semantic search not registered as an MCP tool) |

## Hybrid proof — `hybrid proof` (exit 0, proof_passed=true)

| check | result |
|---|---|
| deterministic count | 3 |
| semantic count | 3 |
| assembles final answer | **false** |
| semantic_retrieval_bypassed_policy | **0** |
| run record guard-clean (23 guards) | true |
| result records guard-clean (23 guards) | true |
| no forbidden persisted columns | true |
| raw query not persisted (only hash) | true |
| no-applied-index → semantic skipped | true |
| deterministic-only mode skips semantic | true |
| unsafe semantic node dropped | true |

## Real HuggingFace hybrid query smoke (`BAAI/bge-small-en-v1.5`)

A genuine local embed + semantic retrieval over the applied `SimpleVectorStore` returned `status='ok'`,
3 deterministic + 3 semantic, `assembles_final_answer=false`, with **real** cosine scores bucketed
**high/medium** (not the uniform MockEmbedding scores). Captured at
`validation-outputs-prompt-20/real-huggingface-hybrid-smoke.json`. Automated equivalent:
`tests/test_phase_09_hybrid_broker.py::test_hybrid_real_huggingface_query_smoke` (marked `integration`).

## Operator DB outcome

`hybrid status` → `deterministic_ready=true`, `semantic_ready=false`
(blocker `semantic_no_applied_index`). `hybrid search` → `ok` with deterministic results and an empty
semantic set; **persists nothing**. `hybrid_query_runs` / `hybrid_query_results` stay **0 rows**; schema
38; operator DB data unmutated.

## Validation matrix

- `python -m compileall src tests` → exit 0
- `ruff check .` → All checks passed!
- `mypy src` → Success: no issues found in **288** source files
- `pytest -m "not live and not integration and not manual"` → **3142 passed, 0 failed, 3 deselected**
- `construction-agent validate --json` → exit 0 (schema 38)
- `construction-agent data-quality table-inventory --json` → exit 0 (contract_table_count=190, 0 unmapped)
- `construction-agent data-quality no-writeback-proof --json` → exit 0
- `second-brain data-quality phase-08a-gates --json` → exit 0
- `second-brain data-quality phase-08b-gates --json` → exit 0
- `second-brain data-quality phase-08c-gates` → **SKIPPED** (mutates operator DB: ~1,299 ledger rows/call)
- `second-brain data-quality phase-08d-gates --json` → exit 0
- `second-brain mcp no-raw-access --json` → exit 0
- `second-brain mcp no-writeback --json` → exit 0
- `second-brain retrieval hybrid status --json` → exit 0 (deterministic ready; semantic blocked: no applied index)
- `second-brain retrieval hybrid search "<q>" --json` → exit 0 (deterministic results; semantic empty; no persist)
- `second-brain retrieval hybrid search "<q>" --mode deterministic-only --json` → exit 0 (semantic skipped)
- `second-brain retrieval hybrid proof --json` → exit 0 (`proof_passed=true`)
- post-CLI guard re-run (`test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof`) → pass

> The prompt's exact-command list used stale MCP paths (`mcp data-quality …`); the real commands are
> `second-brain data-quality phase-08d-gates`, `second-brain mcp no-raw-access`, `second-brain mcp
> no-writeback` — all run, all exit 0.

## Deferred

- Wiring the hybrid broker into Research Packet (A02) / Answer Synthesis (A04) — behavior change, later prompt.
- `generated_outputs` (research-packet) loader still absent — the semantic corpus is Obsidian + reviewed memory only.
- Eval sets, benchmarks, memory-quality review — later Phase 09 prompts.
