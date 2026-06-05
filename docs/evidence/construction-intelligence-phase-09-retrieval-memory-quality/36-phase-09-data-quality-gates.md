# Phase 09 Prompt 36 — Phase 09 Data Quality Gates

**Objective:** Implement Phase 09 gates with pass/warning/fail/deferred taxonomy.

- Schema: **V39** (verified via `construction-agent validate`)
- Package: `1.4.0-phase-09`

## Design — read-only evaluator, no migration, isolated module

New module `src/hb_assistant/construction/second_brain/phase_09_gates.py` adds
`second-brain data-quality phase-09-gates`, mirroring the 08A/08B/08C/08D gate evaluators. No
migration (schema stays **V39**), no new table (`table-inventory` count stays **190**), read-only —
it persists nothing and re-runs no heavy proof fixtures. It checks schema readiness
(`build_phase_09_schema_status_report`), guard-column cleanliness (read-only `SUM` over the 22
Phase-09 tables), contract presence, and table population.

## Gate set (23 gates ≥ contract minimum 18)

**7 structural/safety (must pass):** `phase_09_schema_present` (schema ≥ V39 + all 22 tables + 23
guards), `phase_09_guard_columns_clean` (23 guard columns sum to 0), `no_raw_vector_content`
(`raw_vector_content_persisted`=0), `no_external_writeback_posture` (6 writeback/API guards=0),
`no_semantic_retrieval_bypass` (`semantic_retrieval_bypassed_policy`=0), `gates_contract_loaded`,
`lifecycle_contract_loaded`.

**16 per-surface:** `pass` for static enforcement policies (embedding policy / metadata filter /
context budget / hallucination risk) and the no-raw-vector proof; `deferred_not_blocking` for
table-backed surfaces whose substrate ships empty (the honest Phase-09 state); `fail_blocking` if a
contract is missing (fail-closed).

`ok` = no fail_blocking; `readiness_overstated` is always **false** (a deferred/failed surface is
never reported ready).

## Results

- `second-brain data-quality phase-09-gates --json` (live operator DB) → exit 0: `ok=true`,
  `proof_passed=true`, **23 gates — 12 pass / 0 warning / 0 fail_blocking / 11 deferred_not_blocking**,
  `readiness_overstated=false`, `required_fields_covered=true`, `phase_09_substrate_status=advisory_empty`.
  `build_phase_09_gates_proof(write_evidence=True)` wrote `phase-09-gates-proof.{json,md}`.
- 6 new tests pass (normal / missing-policy fail-closed / stale-schema fail-closed / unsafe-source
  missing-contract fail-closed / no-raw-no-writeback proof / guard-clean artifacts).

## Validation matrix

| Check | Result |
| --- | --- |
| `compileall src tests` | exit 0 |
| `ruff check .` | exit 1 — **3 B008 in `cli/procore.py` only** (concurrent uncommitted churn; my files clean) |
| `mypy src` | this module clean; only the 2 pre-existing `review_burden_mart.py` errors remain |
| `pytest tests/test_phase_09_data_quality_gates.py` | 6 passed |
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

Full captured outputs: `validation-outputs-prompt-36/`.

## Pre-existing (not introduced by this prompt)

- `ruff check .`: 3 B008 in `cli/procore.py` (concurrent uncommitted edit; my files clean).
- `mypy src`: 2 errors in `review_burden_mart.py` (concurrent review-burden work).
- `pytest` default-safe subset: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7).
- `phase-08b-gates` exit 1 — `automation_executor.py:1485` (pre-existing/environmental).

No stop condition triggered (no raw-content/raw-vector persistence, no writeback, no guard violation,
no semantic-retrieval bypass, readiness never overstated).
