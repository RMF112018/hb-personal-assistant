# 156 — Phase 09 Prompt 35: No Raw Vector Index Proof

## Context

Phase 09 Prompt 35. **Objective:** *Scan DB/index/evidence for raw vector content and prohibited
payloads.*

The vector-index subsystem already enforces that **vectors are written outside SQLite**
(`vector_index.py` `vectors_persisted_to_sqlite=False`; the store lives under the external
`persist_root`), and the V38 tables `second_brain_retrieval_vector_index_runs` / `_items` carry the
`raw_vector_content_persisted` CHECK(=0) guard column plus only metadata (hashes/labels). Prompt 14
already proves the *policy* guardrail. What did not yet exist is a **forensic scan proof** that the
live operator DB, the vector-index metadata, and the committed Phase-09 evidence tree actually
contain no raw vector content and no prohibited payloads. This prompt adds
`second-brain retrieval no-raw-vector-index-proof` and its evidence.

## Decision — proof-only scan, persist to the generic V38 validation-runs table (no migration)

No migration; schema stays **V39**. The proof persists (read-only by default; on `--emit-receipt`) a
single guard-clean gate-summary row to the **generic, previously-unused**
`second_brain_phase_09_validation_runs` table (`gate_count`/`pass_count`/`fail_count`/`overall_status`
+ 23 guards — its column shape exactly fits a multi-gate scan proof; already classified in the
table-lifecycle contracts; `table-inventory` count stays 190).

## Design

New module `construction/second_brain/retrieval/no_raw_vector_index_proof.py`:

- **`scan_db(conn)`** — over every `second_brain_retrieval_*` table: sum the 23 guard columns (must be
  0, focus `raw_vector_content_persisted`); confirm no **exact** `embedding`/`vector`/`raw_vector`
  blob column exists (exact-name match — a metadata column like `embedding_model_label` or the
  `raw_vector_content_persisted` guard is *not* a blob); and forbidden-pattern-scan the safe text
  columns of the two vector tables. Findings carry `table.column` + a pattern label — never the value.
- **`scan_evidence(evidence_dir)`** — forbidden-pattern-scan every `*.json`/`*.md` under the Phase-09
  evidence tree; findings carry the file name + label only.
- **Scan patterns** — a deliberately *tight*, signed-URL/secret-specific set (PEM / Bearer-20+ /
  3-part JWT / SAS `sig|sv|se|token=` params / signed-URLs-with-sig|token / oauth secrets),
  mirroring `corpus_balance_mart._FORBIDDEN`. Not the broad financial `https?://` / bare-email
  patterns, which would false-positive across a docs tree (the live run scanned **383** evidence
  files with **0** false positives).
- **`build_no_raw_vector_index_proof(db_path=None, *, evidence_dir=None, write_evidence=True,
  emit_receipt=False)`** — runs the **live arm** (`scan_db` over the operator DB + `scan_evidence` +
  a `vectors_outside_sqlite` attestation derived from the no-blob-column result) and a **non-vacuity
  arm** (`_non_vacuity_check` plants a runtime-assembled synthetic signed-URL into a temp DB text
  column and a temp evidence file and asserts both scanners flag it). Six gates → `gate_count`/
  `pass_count`/`fail_count`/`overall_status`; `proof_passed` = all gates pass. Writes guard-clean
  `no-raw-vector-index-proof.{json,md}` via the strict `_assert_no_raw` gate.
- Custom `NoRawVectorIndexProofError` (fail-closed); contract registered with one line in
  `contracts.PHASE_09_CONTRACT_FILES`. CLI: a single `retrieval no-raw-vector-index-proof` command
  (matching the validation-matrix string).

## Validation

Schema V39; `construction-agent validate` 4/4; `table-inventory` **190 / 189 unchanged** (no new
table; the 3 unmapped tables are concurrent `second_brain_review_burden_*`). New surface (live, over
the real operator DB + evidence tree): `proof_passed=true`, 6/6 gates, **14 retrieval tables**
guard-checked with 0 violations, 0 vector-blob columns, 0 forbidden findings across **383** evidence
files, non-vacuity arm flags the plant. 6 new tests (normal / missing-policy / stale-schema /
unsafe-source scanner detection / no-raw-no-writeback proof + guard-clean row / guard-clean
artifacts). compileall exit 0; my module ruff/mypy-clean.

### Pre-existing/concurrent, not introduced by this prompt

- `ruff check .`: 3 B008 errors in `cli/procore.py` (concurrent uncommitted edit — `procore.py` is
  dirty in the working tree; my files are ruff-clean).
- `mypy`: `review_burden_mart.py:169,171`.
- `pytest`: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7).
- `second-brain data-quality phase-08b-gates` exit 1 — `automation_executor.py:1485`.
- `phase-08c-gates` **skipped** (mutates the operator DB).

Evidence: `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`
(`35-no-raw-vector-index-proof.{json,md}`, `no-raw-vector-index-proof.{json,md}`,
`validation-outputs-prompt-35/`).
