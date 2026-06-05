# 157 — Phase 09 Prompt 36: Phase 09 Data Quality Gates

## Context

Phase 09 Prompt 36. **Objective:** *Implement Phase 09 gates with pass/warning/fail/deferred
taxonomy.*

Phases 08A/08B/08C/08D each expose a data-quality gate evaluator
(`second-brain data-quality phase-08X-gates`) that aggregates conformance checks into the
pass / warning / fail_blocking / deferred_not_blocking taxonomy and reports `ok` +
`readiness_overstated`. Phase 09 had many standalone surfaces (retrieval, memory, proofs) and 22
V38/V39 tables — but no unified Phase-09 gate set. This prompt adds
`second-brain data-quality phase-09-gates`.

## Decision — read-only evaluator, no migration, isolated module

No migration; schema stays **V39**; `table-inventory` count stays **190**. The evaluator is
**read-only** (like the 08A/08D gate dashboards) — it does **not** persist and does **not** re-run
the heavy proof fixtures (vector-index apply, hybrid-with-embeddings). It checks schema readiness,
guard-column cleanliness (read-only `SUM` over the 22 Phase-09 tables), contract presence, and table
population, keeping the command fast and side-effect-free. To avoid the shared `data_quality.py`
concurrency hotspot, the evaluator lives in a **new module**
`construction/second_brain/phase_09_gates.py`.

## Design

`evaluate_phase_09_data_quality_gates(*, db_path=None)` returns the established conformance-report
shape (`gates` / `by_field_status` / `status_counts` / `required_fields_covered` /
`readiness_overstated` / `ok`). 23 gates (≥ the contract's `gate_count_minimum` of 18):

- **7 structural/safety (pass | fail_blocking):** `phase_09_schema_present` (schema ≥ V39 + all 22
  tables + 23 guards, via `build_phase_09_schema_status_report`), `phase_09_guard_columns_clean` (the
  23 guard columns sum to 0 across all 22 tables), `no_raw_vector_content`
  (`raw_vector_content_persisted` = 0), `no_external_writeback_posture` (the 6 writeback/API guard
  columns = 0), `no_semantic_retrieval_bypass` (`semantic_retrieval_bypassed_policy` = 0),
  `gates_contract_loaded`, `lifecycle_contract_loaded`.
- **16 per-surface conformance:** `pass` if the surface's contract loads AND it is a static
  enforcement policy (embedding policy / metadata filter / context budget / hallucination risk) or a
  passing proof (no-raw-vector); `deferred_not_blocking` when a table-backed surface's substrate ships
  empty (the honest Phase-09 state); `fail_blocking` if the contract is missing (fail-closed).

`build_phase_09_gates_proof` wraps the evaluator, sets `proof_passed` = `ok` and not
`readiness_overstated` and `gate_count ≥ minimum` and `required_fields_covered`, and writes
guard-clean `phase-09-gates-proof.{json,md}`. `readiness_overstated` is always false — deferred gates
never pass, so no surface is reported ready while empty/failing.

## Validation

Schema V39; `construction-agent validate` 4/4; `table-inventory` **190 / 189 unchanged** (the 3
unmapped tables are concurrent `second_brain_review_burden_*`). New surface on the live operator DB:
`ok=true`, `proof_passed=true`, **23 gates — 12 pass / 0 warning / 0 fail_blocking / 11
deferred_not_blocking**, `readiness_overstated=false`, `required_fields_covered=true`. 6 new tests
(normal / missing-policy fail-closed / stale-schema fail-closed / unsafe-source missing-contract
fail-closed / no-raw-no-writeback proof / guard-clean artifacts). compileall exit 0; my module
ruff/mypy-clean.

### Pre-existing/concurrent, not introduced by this prompt

- `ruff check .`: 3 B008 errors in `cli/procore.py` (concurrent uncommitted edit; my files clean).
- `mypy`: `review_burden_mart.py` (2 errors).
- `pytest`: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7).
- `second-brain data-quality phase-08b-gates` exit 1 — `automation_executor.py:1485`.
- `phase-08c-gates` **skipped** (mutates the operator DB).

Evidence: `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`
(`36-phase-09-data-quality-gates.{json,md}`, `phase-09-gates-proof.{json,md}`,
`validation-outputs-prompt-36/`).
