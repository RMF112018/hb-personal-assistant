# Phase 09 — Retrieval (LlamaIndex) Setup Runbook

Operator runbook for the **optional** LlamaIndex retrieval layer introduced in Phase 09 Prompt 13.
The base install is fully functional **without** LlamaIndex (local-first default); installing the
optional extra only enables the later Phase 09 vector-index / hybrid-retrieval build paths. Nothing in
this runbook builds an index, computes an embedding, or mutates the operator database.

## 1. Check status (safe; default — no install needed)

```bash
hb-assistant second-brain retrieval llamaindex status --json
```

Reports (read-only):
- `sdk.available` — whether `llama-index-core` is importable (probed without importing it). `false` is
  the normal default.
- `config` + `config_hash` — the resolved metadata-only retrieval config (embedding provider/label,
  index kind, vector store kind, chunk size/overlap). Labels only — no paths or secrets.
- `schema_ready` — the V38 retrieval substrate is present.
- `ready_to_index` — `true` only when the SDK is installed **and** the config is valid **and** the
  schema is ready.
- `blockers` — e.g. `llama_index_not_installed`, `config_invalid`, `schema_not_ready`.

Exit code: `0` when the contract/seed load, the config is valid, and the schema is ready (regardless of
SDK presence); `3` on a fail-closed contract/seed failure, an invalid config, or a stale schema.

## 2. Install the optional retrieval extra (operator-run, optional)

```bash
pip install -e ".[retrieval]"        # llama-index-core
# or, to add a local embedding integration:
pip install -e ".[retrieval-local]"  # llama-index-core + llama-index-embeddings-huggingface
```

After installing, `status` reports `sdk.available=true` and a version; `ready_to_index` becomes `true`
once the config + schema checks also pass. The build/apply paths that consume this are introduced in
later Phase 09 prompts.

## 3. Configuration

The resolved config lives in `resources/config/phase_09_llamaindex_config.seed.yaml` (validated against
`src/hb_assistant/resources/json/phase_09_llamaindex_config_contract.json`). It is metadata-only —
model/index **labels** and bounded numeric params, never raw content, URLs, tokens, or filesystem
paths. To point at an alternate config during testing, set `HB_SECOND_BRAIN_LLAMAINDEX_CONFIG` to a
seed file path.

## Guardrails

- Optional + lazy: the SDK is imported only inside Phase 09 retrieval code paths; the base install,
  migrations, and full test suite run with it absent.
- Read-only: the status surface opens the database read-only and persists nothing.
- Local-first: `embedding_provider: local` by default. External providers
  (`openai` / `azure_openai` / `huggingface_remote`) are **deferred** — selecting one is flagged as an
  invalid config until they are explicitly policy-gated, receipt-backed, and restricted to
  approved/redacted/source-linked chunks.

## Handoff to later Phase 09 prompts

Config-snapshot persistence into `second_brain_retrieval_llamaindex_config_snapshots`, the vector-index
build (dry-run/apply), hybrid retrieval, and evaluation are owned by later Phase 09 prompts (15–39).
