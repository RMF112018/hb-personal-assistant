# 133 — Phase 09 Prompt 14: Embedding and Vector Store Policy + No-Raw Guardrails

**Status:** Implementation — embedding/vector-store policy + no-raw guardrail enforcement + proof (no retrieval runtime built).
**Schema:** V38 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `b192c19`, Prompt 13 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/14-embedding-and-vector-store-policy.md` (+ `.json`, `embedding-vector-policy-no-raw-proof.{json,md}`, `validation-outputs-prompt-14/`).
**Builds on:** records 131 (V38 substrate) + 132 (LlamaIndex config); reuses the shared `_FORBIDDEN` scanner, `_assert_no_raw`, `reasoning.FORBIDDEN_REFERENCE_FIELDS`, `retrieval/policy.py` allowlist/excluded sets.

---

## 1. Purpose

Phase 09's semantic-retrieval plane must embed and index only approved, redacted, source-linked content,
and must never persist raw bodies / prompts / responses / URLs / tokens / secrets / vector blobs in
SQLite. The policy and its no-raw guardrails have to exist and be proven before any index is built
(Prompts 18–19) and before the approved source manifest is selected (Prompt 15). This record documents
the policy (contract + seed + loader), the enforcement primitive, a read-only status surface, and a
fail-closed no-raw proof — with no embeddings computed and no index built.

## 2. Design

### Policy as contract + seed (reusing established loaders)
A JSON contract fixes allowed providers / vector stores / embedding-dim bounds / required + forbidden
node fields / persistence rules / global requirements; a YAML seed holds the resolved metadata-only
values (provider `local`, dim 384, store `simple`, the embeddable family allowlist, a `persist_dir`
*label*). Both load fail-closed (`EmbeddingVectorPolicyError`) via the same `PathPolicy` +
`load_phase_09_contract` patterns used by the LlamaIndex config.

### The no-raw guardrail primitive
`validate_embedding_candidate` is the single enforcement point reused by the build prompts: it returns
the policy violations for a candidate node (empty ⇒ safe). It composes existing safety primitives
rather than forking them — the shared `_FORBIDDEN` regex (raw/secret/URL shapes),
`FORBIDDEN_REFERENCE_FIELDS`, and `EXCLUDED_FAMILIES` — and adds the Phase 09 specifics (embeddable
allowlist = the 7 redacted reader-backed families ∩ broker allowlist − EXCLUDED; vector-blob keys;
required source-linked metadata; review gating). The embeddable set is the policy *maximum*; Prompt 15
narrows it to the selected approved manifest.

### Vectors never in SQLite
The persistence rules encode that the SQLite ledger (`vector_index_items` etc.) is metadata-only and
the vector store lives outside SQLite (under Application Support); the V38
`raw_vector_content_persisted` guard CHECK(=0) enforces it at the storage layer. The status probe is
read-only (`mode=ro`) and the proof is in-memory — neither writes to the operator DB.

### Proof discipline
`build_no_raw_vector_policy_proof` exercises the guard over a safe candidate + eight planted-unsafe
candidates and writes a guard-clean JSON+MD companion (running `_assert_no_raw` before writing). The
planted "secret shape" is assembled at runtime so no literal token appears in scanned source — keeping
the repo sensitive scanner and the second-brain no-writeback source scan clean while still exercising
the guard.

## 3. Verification

Live: `embedding-policy status` → config_valid + schema_ready, 7 embeddable families, governed tables 0
rows; `no-raw-proof` → proof_passed, 9 cases (safe passes, 8 unsafe rejected). Full matrix:
compileall/ruff clean, mypy 283 files, pytest **3091 passed** (3080 + 11 new),
`construction-agent validate` 4/4 V38, table-inventory 190 / 0 unmapped, 08A/08B/MCP gates +
no-raw/no-writeback proofs pass. Operator DB pristine (schema 38; the three governed tables 0 rows).
`phase-08c-gates` skipped (mutating ledger).

## 4. Guardrails & stop conditions

Policy + guardrail + proof only — no embeddings, no index; read-only over the DB, persists nothing;
metadata-only; vectors never in SQLite; external providers deferred + flagged invalid if selected;
EXCLUDED raw families hard-rejected; review tier / confidence / source refs / freshness preserved as
required node metadata. No stop condition triggered.
