# Phase 09 Prompt 35 — No Raw Vector Index Proof

**Objective:** Scan DB/index/evidence for raw vector content and prohibited payloads.

- Repo SHA: `f98d112aa9f068b072af0ea996370edbdfbbf4f5`
- Schema: **V39** (verified via `construction-agent validate`)
- Package: `1.4.0-phase-09`

## Design — proof-only forensic scan, reuse the generic V38 validation-runs table (no migration)

New module `src/hb_assistant/construction/second_brain/retrieval/no_raw_vector_index_proof.py`
forensically scans the operator DB, the vector-index metadata, and the Phase-09 evidence tree. No
migration, schema stays **V39**; on `--emit-receipt` it persists a guard-clean gate-summary row to
the reserved, previously-unused `second_brain_phase_09_validation_runs` table (`table-inventory`
count stays **190**). Findings carry `table.column` / file locations + a pattern label — never the
offending value.

**Six gates:**

| Gate | Meaning | Result |
| --- | --- | --- |
| `db_guard_clean` | every `second_brain_retrieval_*` table's 23 guard columns sum to 0 (esp. `raw_vector_content_persisted`) | true (14 tables, 0 violations) |
| `no_vector_blob_columns` | no **exact** `embedding`/`vector`/`raw_vector` column in SQLite (metadata cols like `embedding_model_label` are not blobs) | true (0 found) |
| `vectors_outside_sqlite` | vectors persist only in the external store, never SQLite | true |
| `db_text_no_forbidden` | the vector tables' safe text columns carry no secrets/PEM/JWT/signed-URLs | true (2 tables) |
| `evidence_no_forbidden` | same scan over the Phase-09 evidence tree | true (383 files, 0 findings) |
| `scanner_detects_planted` | non-vacuity: a runtime-assembled synthetic signed-URL is planted and the scanner flags it | true |

The scan patterns are a deliberately **tight**, signed-URL/secret-specific set (PEM / Bearer-20+ /
3-part JWT / SAS `sig|sv|se|token=` params / signed-URLs / oauth secrets) — not the broad financial
`https?://`/bare-email patterns, which would false-positive across a docs tree. The live run scanned
383 evidence files with **0** false positives.

## Results

- `second-brain retrieval no-raw-vector-index-proof --json` (live, over the real operator DB +
  evidence tree) → exit 0: `proof_passed=true`, `overall_status=clean`, **6/6 gates**, 14 retrieval
  tables guard-checked / 0 violations, 0 vector-blob columns, 383 evidence files scanned / 0 findings,
  non-vacuity arm flags the plant. Wrote `no-raw-vector-index-proof.{json,md}`.
- 6 new tests pass (normal / missing-policy fail-closed / stale-schema fail-closed / unsafe-source
  scanner detection with value-not-echoed / no-raw-no-writeback proof + guard-clean persisted row /
  guard-clean artifacts).

## Validation matrix

| Check | Result |
| --- | --- |
| `compileall src tests` | exit 0 |
| `ruff check .` | exit 1 — **3 B008 in `cli/procore.py` only** (concurrent uncommitted churn; my files are ruff-clean) |
| `mypy src` | this module clean; only the 2 pre-existing `review_burden_mart.py:169,171` errors remain |
| `pytest tests/test_phase_09_no_raw_vector_index_proof.py` | 6 passed |
| `construction-agent validate --json` | exit 0, 4/4, schema **V39** |
| `data-quality table-inventory --json` | 190 contract / 189 live; unmapped = 3 concurrent `review_burden` tables (not ours) |
| `data-quality no-writeback-proof --json` | exit 0 |
| `second-brain data-quality phase-08a-gates --json` | exit 0 |
| `second-brain data-quality phase-08b-gates --json` | exit 1 — pre-existing `automation_executor.py:1485` |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** — mutates operator DB |
| `second-brain data-quality phase-08d-gates --json` | exit 0 |
| `second-brain mcp no-raw-access --json` | exit 0 |
| `second-brain mcp no-writeback --json` | exit 0 |
| `pytest tests/test_repo_sensitive_scan.py tests/test_second_brain_no_writeback_proof.py` | pass |

Full captured outputs: `validation-outputs-prompt-35/`.

## Pre-existing (not introduced by this prompt)

- `ruff check .`: 3 B008 errors in `cli/procore.py` (concurrent uncommitted edit — `procore.py` is
  dirty in the working tree). My files are ruff-clean.
- `mypy src`: 2 errors in `review_burden_mart.py:169,171` (concurrent review-burden work).
- `pytest` default-safe subset: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7).
- `phase-08b-gates` exit 1 — `automation_executor.py:1485` (pre-existing/environmental).

No stop condition triggered (no raw vector content / prohibited payload found in DB or evidence; the
scanner is proven non-vacuous).
