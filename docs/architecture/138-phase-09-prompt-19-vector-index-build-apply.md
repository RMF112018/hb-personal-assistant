# 138 — Phase 09 Prompt 19: Vector Index Build Apply

**Status:** Implementation — policy-gated apply build (embed + vector store + receipts); fail-closed, vectors outside SQLite.
**Schema:** V38 (unchanged). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `b0430c9`, Prompt 18 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/19-vector-index-build-apply.md` (+ `.json`, `vector-index-apply-proof.{json,md}`, `validation-outputs-prompt-19/`).
**Builds on:** record 137 (dry-run); reuses `_build_plan`, the Obsidian + reviewed-memory loaders, `build_approved_source_manifest`, `validate_embedding_candidate`, the LlamaIndex config, and `_FORBIDDEN`/`_assert_no_raw`.

---

## 1. Purpose

The apply build is the write path the dry-run scaffolds. It embeds the approved manifest's loader nodes
via LlamaIndex, writes a vector store **on the local filesystem under Application Support (never to
SQLite)**, and persists metadata-only receipts: one `status='applied'` `vector_index_runs` row plus one
`vector_index_items` row per node. The approved manifest is the only input; every node must carry review
tier / confidence / source ref / freshness metadata and pass the no-raw guardrail. Apply fails closed
(`status='apply_blocked'`, persisting nothing) when the optional SDK is absent, there are no indexable
nodes, or policy/schema is not ready.

## 2. Design

### Reuse the dry-run plan; the apply path adds only the write
`_build_plan` (extracted from the Prompt 18 dry-run) is the single planner: authorization =
`build_approved_source_manifest`; node sources = the two loaders; per-node rule = `_apply_build_rule`
(the four named required fields + `validate_embedding_candidate`). `build_vector_index_apply` calls it,
re-asserts the build rule on every node before embedding (defense in depth), then writes and persists.
No guard logic is forked.

### Injectable writer port; the SDK is the only heavy seam
The embed + vector-store write sits behind a `VectorStoreWriter` callable. The default
(`_llamaindex_vector_writer`) lazy-imports `llama_index.core` (`VectorStoreIndex`, `Document`,
`StorageContext`, `SimpleVectorStore`, `Settings`) and `HuggingFaceEmbedding`, embeds each node's
`text_redacted`, and persists the `SimpleVectorStore` to `persist_dir`. Proofs/tests inject
`_mock_vector_writer` (the same LlamaIndex pipeline with `MockEmbedding`) so the default-safe suite runs
fully offline. The configured model is local `BAAI/bge-small-en-v1.5` (dim 384); a real-model embed is
proven in evidence and an `integration`-marked smoke.

### Vectors live outside SQLite; receipts are metadata-only
The vector store is written to `PathPolicy().get_app_support()/retrieval/vector_store/<run_id>/`. SQLite
receives only hashed/metadata receipts: the run row (`item_count`, `config_hash`, manifest id) and per-node
item rows (`source_ref_hash` — never the raw ref, `content_hash`, `confidence_class`, `freshness_label`,
`chunk_count`). The V38 `raw_vector_content_persisted` CHECK(=0) and the other 22 guard columns stay 0;
`text`, `embedding`, `vector`, `source_ref`, and `persist_dir` are in the contract's forbidden-persisted
list and never written.

### Fail-closed posture
`apply_blocked` is returned (nothing persisted) for `sdk_not_available`, `no_indexable_nodes`,
`schema_not_ready`, or `policy_unavailable`. On the operator DB (zero approved sources) apply blocks with
`no_indexable_nodes` — the honest outcome — leaving the operator DB data-pristine.

## 3. Contract & seed

`phase_09_vector_index_apply_contract.json` (+ `.seed.yaml`) defines the persisted run/item column
allowlists, the forbidden-persisted-fields set, the allowed status values (`applied`, `apply_blocked`),
the blocker-reason vocabulary, and the `external_filesystem` vector-store requirement. Registered as
`vector_index_apply_contract` in `PHASE_09_CONTRACT_FILES`.

## 4. CLI

`second-brain retrieval llamaindex build --apply` embeds + persists (exit 0 on `applied`; exit 3 on
`apply_blocked`/`not_ready`). `build-apply-proof` runs the offline (MockEmbedding) proof. The dry-run
(`build`) path is unchanged.

## 5. Validation

`compileall`/`ruff`/`mypy` (287 files) clean; `pytest -m "not live and not integration and not manual"`
= 3135 passed, 0 failed. `build-apply-proof` passes (3 items, dim 384, vectors outside SQLite,
guard-clean run + item rows, blocked-no-nodes path). Real `bge-small` embed smoke applied 3 items and
wrote the `SimpleVectorStore` JSON to disk. Operator DB unmutated (apply blocked, schema 38, vector
tables 0/0). The full matrix is in the evidence bundle.

## 6. Deferred

Generated-outputs loader (research packets + applied source-linked daily briefs) is now wired into gather
and dry-run/apply paths (see 137 for details). Apply remains gated by SDK presence + indexable nodes +
all existing build-rule/guard passes; no change to apply safety surface.

Hybrid query / retrieval read path, eval sets, benchmarks, and memory-quality review are later Phase 09
prompts.

The generated-outputs loader feeds the same apply writer path (in-memory redacted `text_redacted` only;
`summary_redacted` for packets, joined handoff `title_redacted` for briefs). All nodes still re-assert the
full build rule and embedding guard before any embedding or vector write. The test in 137 (node count
increase on applied brief fixture) also validates that apply would see the additional nodes if SDK + other
gates allow.

## LlamaIndex readiness truthful across installs (post-Prompt 19/20 follow-up)

**This prompt's apply surface made truthful (follow-up after 18/19/20 + 132).** Original: early gate only
checked `_llama_index_available()` (core) → `sdk_not_available`; bare `from llama_index.embeddings.huggingface`
in `_llamaindex_vector_writer` after core try (would traceback on `[retrieval]`-only for real --apply, and
CLI only caught VectorIndexBuildError so unhandled ImportError); `ready_to_apply` overstated on core-only.

Changes (see vector_index.py, llamaindex_config, cli): split gate (core absent → `sdk_not_available`;
core ok + local absent on default writer → `local_embedding_not_ready`); guard HF import (raise
VectorIndexBuildError with hint if `_local_embedding_available()` false); plan now carries
`local_embedding_available` and truthful `ready_to_apply = core and local and nodes`; _mock writer
unchanged (still core-only for proofs). `build-apply-proof` (always injects Mock) remains runnable after
just `[retrieval]`.

**Modeled directly on 121 §3 MCP gap+resolution** (unconditional absent asserts → state-aware on
find_spec; present/absent both covered; `ready_to_*` made truthful rather than post-install surprising).

`build-apply-proof` explicitly documents it uses Mock so it does not require `retrieval-local`. Real
`build --apply` (default writer) now cleanly blocks with the new reason + exit 3.

No schema/contract change. Guardrails: apply still fail-closed, vectors outside SQLite, metadata receipts
only, no-raw re-asserted, honest empty on no nodes. See runbook for install matrix + verification steps
(status/build-proof on base; build-apply-proof after [retrieval]; note real apply needs local).
