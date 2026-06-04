# Phase 09 Prompt 14 — Embedding and Vector Store Policy + No-Raw Guardrails

**Evidence artifact:** `phase_09_embedding_and_vector_store_policy` · **Companion JSON:** `14-embedding-and-vector-store-policy.json`
**No-raw proof companions:** `embedding-vector-policy-no-raw-proof.json` (+ `.md`).
**Classification:** Phase 09 implementation — embedding/vector-store policy + no-raw guardrail enforcement + proof (builds on Prompt 13 LlamaIndex config and the V38 retrieval substrate).
**Schema:** V38 (unchanged). **Version:** 1.3.0.
**Posture:** policy + guardrail + proof; local-only, metadata-only, read-only, fail-closed. **No embeddings computed and no vector index built.**
**Builds on:** records 131 (V38 schema) + 132 (LlamaIndex config); reuses the shared `_FORBIDDEN` scanner, `_assert_no_raw`, `reasoning.FORBIDDEN_REFERENCE_FIELDS`, and `retrieval/policy.py` allowlist/excluded sets.

---

## 1. Purpose

Phase 09's semantic-retrieval plane may embed and index only approved, redacted, source-linked
content — never raw bodies, prompts, responses, URLs, tokens, secrets, or vector blobs in SQLite. Per
package plan `10_VECTOR_INDEX_AND_EMBEDDING_POLICY_PLAN.md`, the policy and its no-raw guardrails must
exist (and be proven) before any index is built (Prompts 18–19) and before the approved source manifest
is selected (Prompt 15). This prompt delivers the policy (contract + seed + loader), the enforcement
primitive (`validate_embedding_candidate`), a read-only status surface, and a fail-closed no-raw proof.

## 2. What changed

### Policy contract + seed
- `src/hb_assistant/resources/json/phase_09_embedding_vector_policy_contract.json` — allowed providers
  (`local`,`mock`), deferred external providers (`openai`,`azure_openai`,`huggingface_remote`), allowed
  vector stores (`simple`), embedding-dim bounds (64–4096), required node metadata fields, forbidden
  node fields (the `FORBIDDEN_REFERENCE_FIELDS` set + `embedding`/`vector`/`raw_vector`), approved
  review statuses, persistence rules (`sqlite_metadata_only`, `raw_vector_content_persisted: 0`,
  `vectors_persisted_outside_sqlite`), and global requirements (local-first, source-linked-only,
  redacted-only, no-external-default, no-raw-vector-in-sqlite, no-semantic-bypass, fail-closed).
- `resources/config/phase_09_embedding_vector_policy.seed.yaml` — `embedding_provider: local`,
  `embedding_dim: 384`, `vector_store_kind: simple`, `max_nodes_per_run: 5000`, the embeddable
  source-family allowlist (the 7 redacted, source-linked reader-backed families — the policy maximum;
  Prompt 15 narrows to the selected manifest), and `persist_dir_label` (a label only, never a path).
- `contracts.py` — registered `embedding_vector_policy_contract` in `PHASE_09_CONTRACT_FILES`.

### No-raw guardrail + status + proof (`retrieval/embedding_policy.py`)
- `validate_embedding_candidate(candidate, *, contract, seed)` — the fail-closed primitive: flags
  excluded / non-embeddable families, missing required metadata, forbidden raw reference fields, raw
  content / secret / signed-URL shapes (via the shared `_FORBIDDEN` scanner), embedding/vector blobs,
  and unresolved review-required items. Empty list ⇒ safe to embed.
- `build_embedding_vector_policy_status(db_path)` — read-only (`mode=ro`): resolved policy, embeddable
  allowlist, persistence rules, config validity, and schema readiness (the three V38 retrieval tables).
- `build_no_raw_vector_policy_proof(write_evidence)` — runs the guard over a controlled safe candidate
  + 8 planted-unsafe candidates (excluded family, non-embeddable family, raw body, signed URL, vector
  blob, secret shape, missing metadata, unresolved review); attests persistence rules; writes a
  guard-clean JSON+MD companion (`_assert_no_raw` runs before writing). In-memory; no DB writes.

### CLI
- New nested sub-group `second-brain retrieval embedding-policy` with `status` and `no-raw-proof`
  (`--evidence/--no-evidence`). Both read-only; exit 0 on success / 3 fail-closed.

## 3. Key results (live)

- `embedding-policy status`: `config_valid=true`, `schema_ready=true`, provider `local`, dim `384`,
  vector store `simple`, **7 embeddable families**, governed tables present with **0 rows**, exit 0.
- `embedding-policy no-raw-proof`: `proof_passed=true`, **9 cases** — the safe candidate passes; all 8
  planted-unsafe candidates are rejected (each with the expected violation). Guard-clean JSON+MD
  written.
- `embeddable_families` excludes every `EXCLUDED_FAMILIES` raw family and the deferred
  meeting-prep/correspondence families.
- Operator DB: schema **38**; the three governed retrieval tables remain **0 rows** — the policy /
  status / proof persist nothing (vectors never enter SQLite).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**283** source files) ·
`pytest -m "not live and not integration and not manual"` → **3091 passed / 0 failed / 1 deselected**
(prior 3080 + 11 new) · `construction-agent validate` 4/4 schema **V38** · `table-inventory` 190 / 0
unmapped · `no-writeback-proof` `proof_passed=true` · `phase-08a-gates`/`phase-08b-gates` ok ·
`mcp no-raw-access`/`mcp no-writeback` `proof_passed=true` · `retrieval embedding-policy status` /
`no-raw-proof` exit 0. `phase-08c-gates` deliberately skipped (mutating append-only ledger — disclosed
Prompts 02/05). Captures under `validation-outputs-prompt-14/`.

The 11 new tests cover: normal path; embeddable allowlist excludes raw; missing-contract +
missing-seed fail-closed; stale-schema not-ready; every unsafe candidate rejected; no-raw-proof
passes + is clean; proof writes guard-clean artifacts; committed policy metadata-only; status/proof
do not mutate the DB; CLI exit codes.

> Note: the no-raw proof's planted "secret shape" candidate assembles a synthetic token shape at
> runtime (never a literal in source) so the repo sensitive scanner and the second-brain no-writeback
> source scan stay clean while the guard is still exercised.

## 5. Guardrails & stop conditions

Policy + guardrail + proof only — no embeddings computed, no index built; read-only over the DB
(`mode=ro`), persists nothing; metadata-only (labels + bounded numbers; no raw content / URL / path /
token / vector blob); vectors never persisted to SQLite; external embedding providers deferred and
flagged invalid if selected; EXCLUDED raw families hard-rejected; review tier / confidence / source
refs / freshness preserved as required node metadata. No stop condition triggered.

## 6. Deferred / owning prompts

External embedding providers — deferred / policy-gated. Approved index-source manifest selection —
Prompt 15. Vector index build (dry-run/apply) — Prompts 18–19. Post-build no-raw-vector-index proof
over the real index — Prompt 35.
