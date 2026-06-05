# 139 — Phase 09 Prompt 20: Hybrid Retrieval Broker

**Status:** Implementation — hybrid retrieval (deterministic + advisory semantic merge); read-only, fail-closed, source-of-truth preserved.
**Schema:** V38 (unchanged). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `3d9e342`, Prompt 19 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/20-hybrid-retrieval-broker.md` (+ `.json`, `hybrid-retrieval-proof.{json,md}`, `validation-outputs-prompt-20/`).
**Builds on:** record 138 (vector index apply); reuses the deterministic `RetrievalBroker` (A03), `RetrievalItem`/`apply_context_budget`/`load_context_budget`, the applied `SimpleVectorStore`, the Prompt 14 `validate_embedding_candidate`, and `_assert_no_raw`.

---

## 1. Purpose

The hybrid broker combines the **deterministic** Retrieval Broker (the source of truth over the
allowlisted families) with an **advisory semantic** path that queries the vector index Prompt 19
persisted to disk. The two result sets merge into one source-linked, guard-clean context, re-bounded by
the existing deterministic budget. Deterministic results are authoritative; semantic results are advisory
"suggested context" only.

## 2. Design

### Compose, don't replace
`build_hybrid_retrieval` calls `RetrievalBroker(db_path).retrieve(emit_receipt=False)` for the
authoritative items, then appends non-duplicate advisory semantic items and re-applies
`apply_context_budget`. The deterministic `broker.py` is untouched.

### Semantic read path (the new seam)
`_semantic_query` locates the newest **applied** `vector_index_runs` store on disk, loads it
(`StorageContext.from_defaults(persist_dir=…)` + `load_index_from_storage` +
`as_retriever(similarity_top_k=k).retrieve(query)`), and embeds the query with the configured local
model. The embedder is **injectable** — the default is `HuggingFaceEmbedding(bge-small)`; proofs/tests
inject `MockEmbedding` so the default-safe suite runs offline. Each match is **source-linked**: its
`ref_doc_id` (= the loader node id) is hashed into the `vector_index_items` `item_id` and looked up to
recover the family / hashed source ref / confidence / freshness from the persisted receipt, then
re-validated with `validate_embedding_candidate` (no-raw + excluded-family drop) before admission.

### Source-of-truth discipline
Semantic items are **floored at review tier 2** (never auto-tier-1 — a suggestion is always at least
review_recommended) and carry only a redacted excerpt + hashed refs. The broker returns a merged
*context*, never a final answer (`assembles_final_answer=False`), so Research Packet (A02) / Evaluation
(A05) discipline is structurally preserved and the `semantic_retrieval_bypassed_policy` guard stays 0.
The hybrid broker is **wiring-ready** (returns the same kind of merged, budgeted context as the
deterministic path) but A02/A04 adoption is deferred to a later prompt.

### Fail-closed, read-only, metadata-only
The whole surface is V38-gated (`HybridRetrievalError` on stale schema / missing policy). The semantic
path is skipped — deterministic still returned — when the SDK is absent (`semantic_sdk_not_available`),
there is no applied index (`semantic_no_applied_index`), or the mode is `deterministic_only`
(`semantic_disabled_mode`). `build_hybrid_retrieval` and `hybrid search` **persist nothing** to the
operator DB; the **raw query is never persisted** (only `query_hash`). Receipt persistence
(`persist_hybrid_query_record` → `hybrid_query_runs` + `hybrid_query_results`, all 23 guard `CHECK(=0)`
columns 0) is exercised in the proof on a temp DB. Vector/semantic search is **not** exposed via MCP.

## 3. Contract & seed

`phase_09_hybrid_retrieval_contract.json` (+ `.seed.yaml`) defines the modes (`deterministic_only`,
`hybrid`), the advisory posture (`deterministic_authoritative`, `semantic_advisory_only`,
`assembles_final_answer=false`, `semantic_min_review_tier=2`), score-bucket thresholds, the run/result
column allowlists, the forbidden-persisted-fields set (raw query, embedding, vector, text, source_ref,
content_excerpt, …), and the skip/blocker reasons. Registered as `hybrid_retrieval_contract`.

## 4. CLI

`second-brain retrieval hybrid status | search "<q>" [--mode hybrid|deterministic-only] | proof`. `search`
emits a metadata-only summary (no raw query, no excerpts) and does not persist; `proof` runs the offline
guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (288 files) clean; `pytest -m "not live and not integration and not manual"`
= 3142 passed, 0 failed. `hybrid proof` passes (3 deterministic + 3 semantic, advisory + source-linked,
guard-clean run + result rows, `assembles_final_answer=false`, `semantic_retrieval_bypassed_policy=0`,
raw query not persisted, all fail-closed paths). A real `bge-small` hybrid query produced high/medium
score buckets. Operator DB unmutated (semantic blocked: no applied index; hybrid tables 0/0; schema 38).
Full matrix in the evidence bundle.

## 6. Deferred

Hybrid broker adoption by A02/A04; the `generated_outputs` loader (semantic corpus = Obsidian + reviewed
memory only); eval sets / benchmarks / memory-quality review — later Phase 09 prompts.

## LlamaIndex readiness truthful across installs (post-Prompt 19/20 follow-up)

**Follow-up after 20 (and 18/19).** The semantic path pre-checked only `_llama_index_available()` (core)
for `semantic_sdk_not_available`, then after core try did bare `from ...huggingface` (potential unhandled
ImportError on core-only install during `_collect_hybrid` / research-packet / output-eval paths that
call hybrid). Status computed `sdk_available` (core) + `semantic_ready = sdk and applied` (overstated
if local missing for default embed).

Changes: precheck tightened to core name; HF import wrapped in try/except returning
`semantic_local_embedding_not_ready`; status now computes local, sets `semantic_ready = core and local
and applied`, appends local blocker when core present but not local, and emits
`local_embedding_available` (sdk_available kept as core for the retrieval extra surface).

**Cites 121 §3** (MCP): unconditional absent → state-aware branching + truthful ready flags that hold
after optional install.

`build_hybrid_retrieval_proof` + `hybrid proof` continue to use injected Mock (core sufficient); real
hybrid semantic (default embed) now requires `retrieval-local` and degrades cleanly with the new
skip_reason. Deterministic path unaffected.

Guardrails preserved (read-only, no persistence on skip, deterministic source of truth, metadata-only,
fail-closed). See updated runbook + 132/137/138 for cross-refs. No schema change.
