# Phase 09 Prompt 13 — LlamaIndex Dependency and Config Surface

**Evidence artifact:** `phase_09_llamaindex_dependency_and_config_surface` · **Companion JSON:** `13-llamaindex-dependency-and-config-surface.json`
**Classification:** Phase 09 implementation — optional dependency declaration + a read-only config/status surface (builds on the V38 substrate from Prompt 12).
**Schema:** V38 (unchanged). **Version:** 1.3.0.
**Posture:** optional extra, **lazy import**, local-only, metadata-only, read-only, fail-closed. **No embeddings / vector index / semantic retrieval** is built — those land in later Phase 09 prompts.
**Builds on:** record 131 (Prompt 12 V38 schema); the optional-`mcp`-SDK lazy-import pattern; the corpus-balance seed + 08x contract loaders.

---

## 1. Purpose

Phase 09's semantic-retrieval plane uses LlamaIndex. Per package plan `08_DEPENDENCY_AND_LLAMAINDEX_INTEGRATION_PLAN.md`, the dependency must be **optional + lazy-imported** so the base install, migrations, daily brief, financial readiness, MCP, and the full test suite all run with **no** LlamaIndex present (local-first default). This prompt declares the optional extra and adds a read-only config/status surface; it does not import LlamaIndex at module load, build any index, or compute any embedding.

Guardrails honored: never persist raw content / prompts / responses / tokens / secrets / URLs / arbitrary SQL / unsafe paths; no external writeback; no raw vector search through MCP; no determinations; review tier / confidence / source refs / freshness / coverage preserved by the surrounding read models (unchanged here).

## 2. What changed

### Optional dependency (`pyproject.toml`)
- New extras, in the `mcp`-extra style, **not installed** in the validation env:
  - `retrieval = ["llama-index-core>=0.12"]`
  - `retrieval-local = ["llama-index-core>=0.12", "llama-index-embeddings-huggingface>=0.3"]`
- A comment documents lazy-import / local-first posture and that external embedding providers stay deferred / policy-gated / receipt-backed.

### Config contract + seed
- `src/hb_assistant/resources/json/phase_09_llamaindex_config_contract.json` — `required_fields`,
  `allowed_embedding_providers` (`local`, `mock`), `allowed_index_kinds` (`vector_store`),
  `allowed_vector_store_kinds` (`simple`), `deferred_embedding_providers`
  (`openai`/`azure_openai`/`huggingface_remote`), and `global_requirements`
  (lazy-import-only, metadata-only, no-raw, no-writeback, no-external-default, local-first,
  source-linked-chunks-only, deferred-external-policy-gated).
- `resources/config/phase_09_llamaindex_config.seed.yaml` — resolved values: `embedding_provider: local`,
  `embedding_model_label: BAAI/bge-small-en-v1.5` (label only), `index_kind: vector_store`,
  `vector_store_kind: simple`, `chunk_size: 512`, `chunk_overlap: 64`,
  `persist_dir_label: app_support_retrieval_index` (a **label**, never a real path). No raw content /
  URL / token / filesystem path.
- `contracts.py` — `PHASE_09_CONTRACT_FILES` + `load_phase_09_contract`.

### Helper + CLI (read-only, lazy, fail-closed)
- `construction/second_brain/retrieval/llamaindex_config.py`:
  `_llama_index_available()` (probes via `find_spec("llama_index")` — import-free),
  `_llama_index_version()` (`importlib.metadata`), fail-closed `load_llamaindex_config_contract()` /
  `load_llamaindex_config_seed()`, and `build_llamaindex_config_status(db_path=None)` — validates the
  config against the contract, computes a stable `config_hash` (sha256 of the canonical config),
  reads schema readiness `mode=ro`, and reports `ready_to_index` + `blockers`. Persists nothing.
- CLI `second-brain retrieval llamaindex status --json` (new two-level group
  `retrieval` → `llamaindex`). Exit 0 when contract/seed load, config is valid, and schema is ready;
  exit 3 on a fail-closed contract/seed failure, invalid config, or stale schema. SDK-absent is
  reported, not failed.

## 3. Key results (live, SDK absent — the expected default)

- `retrieval llamaindex status`: `sdk.available = false`, `config_valid = true`,
  `schema_ready = true`, `ready_to_index = false`, `blockers = ["llama_index_not_installed"]`,
  `config_hash = c1aac21b856a…`, `snapshot_row_count = 0`, exit **0**.
- The base install + full suite pass with **no** LlamaIndex installed (lazy import verified).
- Operator DB: schema **38**, `second_brain_retrieval_llamaindex_config_snapshots` **0 rows** — the
  status surface persists nothing (read-only `mode=ro`).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**282** source files) ·
`pytest -m "not live and not integration and not manual"` → **3080 passed / 0 failed / 1 deselected**
(prior 3069 + 11 new) · `construction-agent validate` 4/4 schema **V38** ·
`table-inventory` 190 contract / 0 unmapped · `no-writeback-proof` `proof_passed=true` ·
`phase-08a-gates` / `phase-08b-gates` ok · `mcp no-raw-access` / `mcp no-writeback` `proof_passed=true` ·
`retrieval llamaindex status` exit 0. `phase-08c-gates` deliberately skipped (its append-only ledger
writes the operator DB — disclosed Prompts 02/05). Captures under `validation-outputs-prompt-13/`.

The 11 new tests cover: normal path (config valid + schema ready, stable config_hash, read_only);
missing-contract + missing-seed fail-closed; stale-schema not-ready; unsafe/deferred provider →
config invalid; committed config metadata-only (no URL/path/secret shapes); no-mutation / clean report;
SDK-state-aware (ready_to_index + blockers flip with SDK presence); CLI exit 0/3 + contract-failure.

## 5. Guardrails & stop conditions

Optional extra (not installed); lazy import only (no module-level LlamaIndex import; `find_spec` probe
is import-free); read-only over the DB (`mode=ro`), persists nothing; metadata-only config (labels /
bounded numbers, no raw content / URL / path / token); external embedding providers deferred + flagged
invalid if selected; no embeddings / vector index / semantic retrieval built. No stop condition
triggered.

## 6. Deferred / owning prompts

External embedding providers (openai / azure_openai / huggingface_remote) — deferred, policy-gated.
Config-snapshot persistence into `second_brain_retrieval_llamaindex_config_snapshots` — owned by the
vector-index build prompts (18–19). Vector index build + hybrid retrieval + evaluation — later Phase 09
prompts.
