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

## 4. Embedding & vector-store policy (Prompt 14)

The embedding/vector-store policy governs what may be embedded and how vectors are persisted. Inspect
it (read-only) and run the no-raw guardrail proof:

```bash
hb-assistant second-brain retrieval embedding-policy status --json
hb-assistant second-brain retrieval embedding-policy no-raw-proof --json
```

- `status` reports the embedding provider/dimension/vector-store kind, the embeddable source-family
  allowlist (the redacted, source-linked families — never a raw EXCLUDED family), the persistence rules
  (**vectors are never persisted to SQLite** — the ledger is metadata-only), and schema readiness.
- `no-raw-proof` runs the `validate_embedding_candidate` guard over a safe candidate plus planted-unsafe
  candidates (excluded family, raw body, signed URL, vector blob, secret shape, missing metadata,
  unresolved review) and attests the persistence rules. `--no-evidence` skips writing the proof
  companion. Builds no embeddings; persists nothing.

The policy lives in `resources/config/phase_09_embedding_vector_policy.seed.yaml` (validated against
`src/hb_assistant/resources/json/phase_09_embedding_vector_policy_contract.json`); override it during
testing with `HB_SECOND_BRAIN_EMBEDDING_VECTOR_POLICY`.

## 5. Approved source manifests (Prompt 15)

The approved source manifest enumerates which approved, redacted, source-linked records (generated
outputs, approved Obsidian outputs, reviewed memory) are eligible for indexing. Build it (read-only,
dry-run by default) and run the approval/no-raw proof:

```bash
hb-assistant second-brain retrieval approved-sources build --json          # dry-run (no write)
hb-assistant second-brain retrieval approved-sources proof --json
```

- `build` reports the **metadata-only** manifest — per-family approved/excluded counts + a deterministic
  hash + status + warnings. It excludes unresolved high-impact (tier-3 / `review_required`), non-accepted
  statuses, non-`apply` Obsidian manifests, and raw-content shapes. With no approved sources present the
  manifest is honestly `empty`. `--apply` persists a single guard-clean summary row (metadata-only); the
  default is dry-run (no write).
- `proof` runs `validate_manifest_entry` over controlled safe + planted-unsafe entries and writes a
  guard-clean proof companion. Builds no embeddings/index; persists nothing to the operator DB.

Override the manifest config during testing with `HB_SECOND_BRAIN_APPROVED_SOURCE_MANIFEST`.

## 6. Approved Obsidian output loader (Prompt 16)

The Obsidian loader prepares only approved, source-linked generated Obsidian notes as safe nodes for
the future embed/index step. Inspect it (read-only) and run the apply-only / no-raw proof:

```bash
hb-assistant second-brain retrieval obsidian-loader status --json
hb-assistant second-brain retrieval obsidian-loader proof --json
```

- `status` loads only the entries of the latest **`mode='apply'`** Obsidian index manifest (dry-run /
  unapproved manifests are never loaded) and reports a **metadata-only** node set (counts + per-node
  hashes; no text). Each node is validated by the embedding guardrail (embeddable family, source-linked
  metadata, no-raw, no unresolved high-impact tier-3). With no apply manifest the loader is `empty`.
- `proof` demonstrates an apply-mode fixture index loads nodes while a dry-run-only index loads 0, and
  the guardrail rejects tier-3/raw/non-embeddable candidates. Builds no embeddings; persists nothing.

## 7. Reviewed memory loader (Prompt 17)

The reviewed-memory loader prepares only reviewed (accepted) long-term memory as safe nodes for the
future embed/index step. Inspect it (read-only) and run the reviewed-only / no-raw proof:

```bash
hb-assistant second-brain retrieval memory-loader status --json
hb-assistant second-brain retrieval memory-loader proof --json
```

- `status` loads only `long_term_memory_items` with `review_status='accepted'` (pending/rejected/
  superseded are never loaded) and reports a **metadata-only** node set (counts + per-node hashes; no
  statement text). Each node is validated by the embedding guardrail. With no accepted memory the loader
  is `empty`.
- `proof` demonstrates an accepted-memory fixture loads nodes while a pending-only fixture loads 0, and
  the guardrail rejects non-embeddable/raw/missing-metadata/unresolved candidates. Builds no embeddings;
  persists nothing.

Together with the Obsidian loader (§6) this completes the per-category node-preparation loaders.

## Guardrails

- Optional + lazy: the SDK is imported only inside Phase 09 retrieval code paths; the base install,
  migrations, and full test suite run with it absent.
- Embeddings/vectors: only approved, redacted, source-linked families may be embedded; vectors are
  never written to SQLite (the V38 `raw_vector_content_persisted` guard enforces it).
- Read-only: the status surface opens the database read-only and persists nothing.
- Local-first: `embedding_provider: local` by default. External providers
  (`openai` / `azure_openai` / `huggingface_remote`) are **deferred** — selecting one is flagged as an
  invalid config until they are explicitly policy-gated, receipt-backed, and restricted to
  approved/redacted/source-linked chunks.

## Handoff to later Phase 09 prompts

Config-snapshot persistence into `second_brain_retrieval_llamaindex_config_snapshots`, the vector-index
build (dry-run/apply), hybrid retrieval, and evaluation are owned by later Phase 09 prompts (15–39).
