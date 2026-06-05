# 155 — Phase 09 Prompt 34: Source Linked Retrieval Proof

## Context

Phase 09 Prompt 34. **Objective:** *Prove every retrieval result maps to approved source refs.*

The retrieval subsystem already exists (`construction/second_brain/retrieval/`): the hybrid broker
(`build_hybrid_envelope`/`build_hybrid_retrieval`) merges authoritative deterministic results with
advisory, source-linked semantic results into a `RetrievalEnvelope` of `RetrievalItem`s, each
carrying `source_family` + `source_ref`. A reserved **V38** table
`second_brain_retrieval_source_linked_proof_runs` exists, and the embedded `_source_linked_proof()`
in `synthesis/semantic_output_evaluation.py` (Prompt 23 `output-eval`) already writes to it as part
of broader output evaluation. What did not yet exist is a **standalone** Source-Linked Retrieval
Proof surface — its own contract, CLI, and evidence — that proves in isolation that every retrieval
result maps to an approved source ref.

## Decision — standalone surface, reuse the reserved V38 table (no migration)

Mirrors Prompt 32 (reuse a reserved V38 table; no migration; schema stays **V39**; `table-inventory`
contract count unchanged at **190** — the table is already classified in both lifecycle contracts).
The contract's required fields (`run_id`, `result_count`, `linked_count`, `unlinked_count`,
`proof_passed`) are emitted in the build/proof JSON; on `--emit-receipt` a metadata-only, guard-clean
summary row persists to `second_brain_retrieval_source_linked_proof_runs` (mapping
result_count→checked_count, linked_count→source_linked_count). Read-only/dry-run by default. The
table is co-owned with `output-eval`; rows use a distinct `slr_` run_id prefix (INSERT OR REPLACE on
the run_id PK — no collision).

## Design

New module `construction/second_brain/retrieval/source_linked_proof.py`, replicating the Phase 09
build+proof skeleton (Prompt 32/33):

- **`_link_status(items)`** — pure linkage accounting reusing the established rule: a result is
  source-linked iff it carries a non-empty `source_ref` and a `source_family` not in
  `EXCLUDED_FAMILIES` (imported from `retrieval/policy.py`). Returns `result_count`, `linked_count`,
  `unlinked_count`, a per-family linked/unlinked breakdown, and a `status` (`source_linked` /
  `unlinked_found` / `empty`). Never emits the raw refs.
- **`build_source_linked_retrieval_proof(db_path=None, *, query=None, project_key=None, mode="hybrid",
  embed_model=None, persist_root=None, emit_receipt=False)`** — fail-closed loads contract+seed,
  schema gate (>= V39 with the proof-runs table), runs `build_hybrid_envelope(query, ...)`, computes
  `_link_status(envelope.items)`, `proof_passed = result_count >= min_results and unlinked_count ==
  0`. Emits a metadata-only summary (counts + hashed run id + `query_hash` (never the raw query) +
  per-family breakdown + a compact `guard_attestation`). Persists on `emit_receipt`.
- **`build_source_linked_retrieval_proof_proof(*, evidence_dir=None, write_evidence=True)`** — seeds a
  controlled temp DB via `vector_index._proof_db` + `build_vector_index_apply(_mock_vector_writer)`,
  runs the build over it with `_mock_embed_model()` (so both deterministic AND semantic results are
  exercised), and asserts: `result_count > 0`, every result source-linked (`unlinked_count == 0`),
  `proof_passed`, no determination, persisted rows guard-clean, read-only default persists nothing,
  and no raw content emitted. Writes guard-clean `source-linked-retrieval-proof.{json,md}`.
- CLI: `second-brain retrieval source-linked build|proof --json` (exit 0 success, 3 fail-closed).

`RetrievalItem` itself forbids raw `source_family` names (a Pydantic validator) — a defence-in-depth
guarantee that the broker can never emit an excluded-family result; `_link_status` is the explicit
proof of it over the returned envelope.

## Validation

Schema V39; `construction-agent validate` 4/4; `table-inventory` **190 / 189 unchanged** (no new
table; `in_db_not_in_contract` is exactly the three concurrent `second_brain_review_burden_*`
tables). New surface: `source-linked build` on the operator DB → status `source_linked`, 1 result,
all linked, `proof_passed=true`; `source-linked proof` → `proof_passed=true` (3 results = deterministic
+ semantic, `unlinked_count=0`, `every_result_source_linked=true`, guard-clean, no-raw). 6 new tests
(normal / missing-policy / stale-schema / unsafe-source linkage accounting / no-raw-no-writeback proof
/ guard-clean artifacts). compileall exit 0; ruff clean; `mypy src` clean for this module (only the 2
pre-existing `review_burden_mart.py:165,167` errors remain).

### Pre-existing/concurrent, not introduced by this prompt

- `mypy`: `review_burden_mart.py:165,167`.
- `pytest`: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7).
- `second-brain data-quality phase-08b-gates` exit 1 — `automation_executor.py:1485`.
- `phase-08c-gates` **skipped** (mutates the operator DB).

Evidence: `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`
(`34-source-linked-retrieval-proof.{json,md}`, `source-linked-retrieval-proof.{json,md}`,
`validation-outputs-prompt-34/`).
