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

## 8. Vector index build — dry run (Prompt 18)

The dry-run vector build plans what would be embedded/indexed over the approved manifest's loader nodes,
**computing no embeddings and writing no vector store**:

```bash
hb-assistant second-brain retrieval llamaindex build --json          # dry-run plan (default)
hb-assistant second-brain retrieval llamaindex build-proof --json
```

- `build` (dry-run by default) reports a metadata-only plan — per-family node counts, planned chunk
  count, config/plan hashes, `ready_to_apply`, `vectors_persisted_to_sqlite: false`. It rejects any node
  lacking review tier / confidence / source ref / freshness / no-raw proof, and the approved manifest is
  the only input. With no approved nodes the plan is honestly empty.
- `build --apply` (Prompt 19) embeds the approved nodes via LlamaIndex, writes a `SimpleVectorStore` on
  the local filesystem under Application Support (`retrieval/vector_store/<run_id>/`, **never SQLite**),
  and persists metadata-only receipts (a `status='applied'` `vector_index_runs` row + one
  `vector_index_items` row per node). It **fails closed** (`status='apply_blocked'`, persisting nothing)
  when the optional SDK is absent (`sdk_not_available`), there are no indexable nodes
  (`no_indexable_nodes`), or policy/schema is not ready. Exit 0 on `applied`; 3 on `apply_blocked`.
- `build-proof` demonstrates the dry-run plan + build rule + a guard-clean `status='dry_run'` run record
  on a controlled fixture; persists nothing to the operator DB.
- `build-apply-proof` demonstrates a guard-clean **apply** on a controlled fixture via an offline
  `MockEmbedding` writer: vectors are written outside SQLite, a `status='applied'` run + per-node item
  rows persist with all 23 guard `CHECK(=0)` columns 0, and the blocked-no-nodes path is exercised;
  persists nothing to the operator DB.

## Hybrid retrieval (Prompt 20)

The `second-brain retrieval hybrid` group combines the deterministic Retrieval Broker (the source of
truth) with an advisory semantic path over the applied vector index. Deterministic results are
authoritative; semantic results are advisory, source-linked suggestions only and the broker never
assembles a final answer (`assembles_final_answer=false`) — answer assembly stays in the Research Packet
/ Evaluation layers.

- `hybrid status` — readiness: deterministic is always ready; semantic is ready only when the SDK is
  installed **and** a vector index has been applied (otherwise `semantic_no_applied_index` /
  `semantic_sdk_not_available`).
- `hybrid search "<query>" [--project P] [--mode hybrid|deterministic-only]` — returns a metadata-only
  summary (counts, per-family + origin split, tier distribution, score buckets, degradation, warnings).
  The raw query is **never persisted** (only its hash), no excerpts are echoed, and **nothing is
  persisted to the operator DB**. The semantic path fails closed (skipped, deterministic still returned)
  when the SDK is absent or there is no applied index.
- `hybrid proof` — demonstrates a guard-clean hybrid query on a controlled fixture (applied index +
  offline `MockEmbedding`): deterministic + advisory semantic results merge, receipts are metadata-only
  with all 23 guard `CHECK(=0)` columns 0, `semantic_retrieval_bypassed_policy=0`, and the
  no-applied-index / deterministic-only / unsafe-node paths are exercised; persists nothing to the
  operator DB.

## Metadata filter enforcement (Prompt 21)

The `second-brain retrieval metadata-filter` group enforces **project / source / date / review /
confidence / source-coverage** filters around the hybrid broker — **before** retrieval (constrain the
allowlisted families/sources queried; reject excluded families) and **after** retrieval (drop items
outside the requested window/tier/confidence; emit source-coverage warnings). It is read-only and
persists nothing; the raw query is never emitted (only its hash); review tier / confidence / source
references / freshness are preserved on kept items.

- `metadata-filter status` — policy view: filterable keys, date-capable families, confidence order
  (`deterministic > high > medium > low > unknown`), review-tier bounds.
- `metadata-filter apply "<query>" [--project P] [--source a,b] [--date-from] [--date-to]
  [--max-review-tier 1|2|3] [--min-confidence high|…] [--require-coverage] [--mode hybrid|deterministic-only]`
  — runs a filtered hybrid retrieval and emits a metadata-only summary (counts, per-family + origin
  split, tier distribution, `dropped_by_reason`, coverage warnings). Date filtering is **family-aware**:
  families whose `recency` is not a date are kept with a `date_filter_not_applicable` warning rather than
  dropped. An explicitly requested **excluded** family fails closed (exit 3).
- `metadata-filter proof` — demonstrates the pre-filter rejection of excluded families and the
  post-filter drop matrix (project / family / date / review / confidence) with recorded reasons +
  coverage warnings; persists nothing.

## Research packet integration (Prompt 22)

The `second-brain retrieval research-packet` group is the sanctioned route for semantic (vector)
retrieval context to enter answer generation: it builds the hybrid (deterministic authoritative +
advisory semantic) envelope and routes it through Research Packet generation (A02) only. The bridge
returns a metadata-only **research packet** (advisory), **never an answer** — semantic results cannot
assemble a final answer outside the Research Packet / Evaluation layers. (This is distinct from the 08A
top-level `second-brain research-packet build` command.)

- `research-packet build "<query>" [--project P] [--source a,b] [--max-review-tier 1|2|3]
  [--min-confidence high|…] [--mode hybrid|deterministic-only]` — routes semantic context into a research
  packet and emits a metadata-only summary (`route='research_packet_only'`, `synthesis_performed=false`,
  `assembles_final_answer=false`, packet advisory/quality/degradation, counts). The raw query is **never**
  emitted (only its hash); **persists nothing** to the operator DB. On the operator DB (no applied vector
  index) semantic is skipped and the packet is built from deterministic context (honest).
- `research-packet proof` — demonstrates semantic context routing into an advisory packet, the route
  returning a packet (not an answer), a guard-clean metadata-only persisted packet receipt, no
  semantic→answer bypass (the synthesis agent has no hybrid-broker reference), and excluded-family
  fail-closed; persists nothing to the operator DB.

## Output evaluation integration (Prompt 23)

The `second-brain retrieval output-eval` group routes semantic (vector) retrieval **outputs** through the
Output Evaluation (A05) layer + an unsupported-claim check + a source-linked proof, persisting
metadata-only receipts to the V38 `source_linked_proof_runs` + `unsupported_claim_checks` tables. The
context is evaluated for fitness but **never synthesized into an answer**; every retrieved item must be a
supported, source-linked claim (zero tolerance) or the run fails closed.

- `output-eval run "<query>" [--project P] [--source a,b] [--max-review-tier 1|2|3]
  [--min-confidence high|…] [--mode hybrid|deterministic-only]` — runs the A05 checklist over a
  non-synthesized context result + the unsupported-claim/source-linked checks, and emits a metadata-only
  summary (`route='evaluation_only'`, `synthesis_performed=false`, `overall_passed`, the checklist,
  `unsupported_count`/`unlinked_count`). The raw query is **never** emitted (only its hash); no answer is
  emitted; **persists nothing** to the operator DB. Exit 0 iff the overall evaluation passes; 3 fail-closed.
- `output-eval proof` — demonstrates the route through the real A05 evaluation + unsupported-claim
  detection (an item without a source ref is detected and blocks), guard-clean metadata-only receipts in
  both V38 tables, no answer assembly, and excluded-family fail-closed; persists nothing to the operator DB.

## Retrieval quality eval set (Prompt 24)

The `second-brain retrieval eval-set` group creates **source-linked retrieval evaluation cases from
approved outputs** (the approved Obsidian + reviewed-memory corpus) — one case per approved node, linked
to its source by a hashed ref. Cases are metadata-only (no raw query/content/source ref — only hashes);
executing/scoring the set against the index (`eval_runs`) is a later prompt. No embeddings are involved.

- `eval-set build [--project P] [--name NAME]` — enumerates the approved outputs and emits a metadata-only
  summary (`status` built/empty, `case_count`, per-family counts, `review_tier` summary). The set name is
  **hashed** (never stored raw); **persists nothing** to the operator DB. On the operator DB (no approved
  outputs) the set is honestly `empty`. Exit 0 on success; 3 fail-closed.
- `eval-set proof` — demonstrates source-linked cases built from approved outputs, guard-clean metadata-only
  `eval_sets` + `eval_cases` receipts, unsafe/unlinked/excluded-family node exclusion, and no raw source
  ref emitted; persists nothing to the operator DB.

## Deterministic vs semantic benchmark (Prompt 25)

The `second-brain retrieval benchmark` group **benchmarks the three retrieval modes — deterministic,
semantic, hybrid — against each other** over the approved corpus and emits **comparative, bucketed,
metadata-only metrics**. It answers "does the semantic/hybrid path add retrieval value over the
deterministic baseline?" — a measurement leaf that assembles no answer (`assembles_final_answer=false`)
and never routes semantic context into an answer / Research Packet / Evaluation path. Probes are built at
runtime from each approved node's already-redacted excerpt and are **never persisted or emitted**; only
seven bucketed `(metric, mode)` rows reach the V38 `benchmark_runs` table.

- `benchmark build [--project P] [--name NAME]` — runs the deterministic baseline once and one advisory
  semantic query per probe over the applied vector index, then emits a metadata-only summary
  (`status` built/blocked/empty, `probe_count`, `metric_row_count`, per-mode `mode_metrics`, semantic
  hit-rate, warnings). The semantic side degrades **fail-closed** (a `blocked` `semantic_status`) when the
  SDK / applied index is absent — the deterministic baseline is unaffected. The benchmark name is
  **hashed** (never stored raw); **persists nothing** to the operator DB. On the operator DB (no approved
  outputs) the benchmark is honestly `empty`. Exit 0 on success; 3 fail-closed.
- `benchmark proof` — demonstrates all three modes compared over an applied index, guard-clean
  metadata-only `benchmark_runs` receipts (all 23 `CHECK(=0)` guards 0; `semantic_retrieval_bypassed_policy`
  0), semantic floored at review tier 2, the blocked-semantic fail-closed path, unsafe-node exclusion, and
  no raw query/probe/content/source ref emitted; persists nothing to the operator DB.

## Project-specific retrieval benchmarks + coverage (Prompt 26)

The `second-brain retrieval project-benchmark` group scopes the Prompt 25 benchmark **per project** and
pairs each with a **coverage report**. It enumerates projects from the approved retrieval corpus and, per
project, runs the deterministic/semantic/hybrid benchmark plus the read-only corpus-balance coverage mart
(per-family `covered`/`empty`/`deferred_no_reader`). Per-project benchmark metrics reuse the existing V38
`benchmark_runs` table (project-distinct run ids); coverage reports are read-only advisory output (never
persisted). It is an orchestration leaf — `assembles_final_answer=false`, semantic context never reaches
an answer / Research Packet / Evaluation path.

- `project-benchmark build [--project P] [--name NAME]` — enumerates projects (or scopes to `--project P`)
  and emits a metadata-only summary (`status` built/empty, `projects_count`, a per-project benchmark +
  coverage report, a cross-project rollup, warnings). The base name is **hashed** (never stored raw);
  **persists nothing** to the operator DB by default. On the operator DB (no approved corpus → no
  projects) it is honestly `empty`. Exit 0 on success; 3 fail-closed.
- `project-benchmark proof` — demonstrates ≥1 project enumerated, per-project guard-clean metadata-only
  `benchmark_runs` receipts (`semantic_retrieval_bypassed_policy` 0), per-project coverage reports present
  + advisory, the read-only default persisting nothing, unsafe/excluded families excluded from coverage,
  and no raw query/probe/content/source ref emitted; persists nothing to the operator DB.

## Installing the optional embedding extra (for `--apply`)

`--apply` needs the LlamaIndex SDK **and** a local embedding model. `.[retrieval]` is core-only;
`.[retrieval-local]` adds the HuggingFace embeddings backend for the configured
`BAAI/bge-small-en-v1.5` (downloads model weights on first use, then runs offline):

```bash
pip install -e ".[retrieval-local]"
```

Without it, `--apply` stays fail-closed (`apply_blocked: sdk_not_available`) and the rest of the surface
(status, dry-run, all proofs) continues to run with the SDK absent.

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

The vector-index build (dry-run + apply) landed in Prompts 18–19. Config-snapshot persistence into
`second_brain_retrieval_llamaindex_config_snapshots`, hybrid retrieval, and evaluation are owned by later
Phase 09 prompts (20–39).
