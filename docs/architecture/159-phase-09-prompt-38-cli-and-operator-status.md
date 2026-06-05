# 159 — Phase 09 Prompt 38: CLI and Operator Status

## Context

Phase 09 Prompt 38. **Objective:** *Expose repo-consistent CLI status/eval/build/proof surfaces.*

Phase 09 built ~24 CLI surfaces across `second-brain retrieval`, `second-brain memory`,
`second-brain agent-performance`, `second-brain daily-brief-reproducibility`, and
`second-brain data-quality`. There were aggregators for **schema** (`phase-09-schema-status`) and
**gates** (`phase-09-gates`), but no single **operator status** giving a repo-consistent view of every
Phase-09 surface, its status/build/proof/eval command shape, and the rolled-up readiness posture. This
prompt adds `second-brain data-quality phase-09-operator-status`.

## Decision — read-only operator-status aggregator, no migration

No migration; schema stays **V39**; `table-inventory` count stays **190**; read-only (persists nothing;
re-runs no heavy forensic proofs). New module
`construction/second_brain/phase_09_operator_status.py` is driven by a **surface registry** (seed)
that mirrors the repo's actual Phase-09 CLI command set (the "repo-consistent" requirement). It reports
each surface's posture (contract present, owning-table population, command kinds) and rolls up the
existing read-only `build_phase_09_schema_status_report` + `build_phase_09_gates_proof` signals into an
honest `overall_status`.

## Design

`evaluate_phase_09_operator_status(*, db_path=None)` returns: `surfaces` (per-surface rows — `name`,
`cli_path`, `kinds`, `contract_present`, `owning_table`, `row_count`, `populated`), `surface_count`,
`surfaces_with` (counts by command kind), `schema_ready`, `gates_ok`, `all_contracts_present`,
`missing_contracts`, `overall_status` (`advisory_ready` when schema_ready ∧ gates_ok ∧
all_contracts_present, else `degraded`/`not_ready`), `operator_status_ok`, `readiness_overstated=false`.

**Readiness is never overstated.** `schema_ready` uses the schema report's structural fields
(`schema_ready` + `all_tables_present` + `all_guards_present`) — deliberately **not** the report's
`overall_status`, which requires `all_rows_zero` (so a legitimately-populated Phase-09 table does not
make the operator status fail). A surface whose substrate ships empty is reported `advisory_ready`,
never `operational`. `build_phase_09_operator_status` writes guard-clean
`phase-09-operator-status.{json,md}` via `_assert_no_raw`. Read-only; advisory; makes no determination;
fail-closed on missing policy or stale schema.

## Validation

Schema V39; `construction-agent validate` 4/4; `table-inventory` **190 / 189 unchanged**. New surface
on the live operator DB: `overall_status=advisory_ready`, `operator_status_ok=true`, **24 surfaces**
(7 status / 14 build / 22 proof / 1 gates), `schema_ready=true`, `gates_ok=true`,
`all_contracts_present=true`, `readiness_overstated=false`. Sample Phase-09 surface commands
(`retrieval llamaindex/embedding-policy/hybrid status --json`) execute exit 0 — confirming the
repo-consistent command set. 6 new tests (normal / missing-policy fail-closed / stale-schema
fail-closed / unsafe-source missing-contract not-overstated / no-raw-no-determination / guard-clean
artifacts). compileall exit 0; my module ruff/mypy-clean.

### Pre-existing/concurrent, not introduced by this prompt

- `ruff check .`: 3 B008 errors in `cli/procore.py` (my files clean).
- `mypy`: `review_burden_mart.py` (2 errors).
- `pytest`: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7) +
  the full-suite test-ordering `daily_brief_*`/`agent_receipts` failures (all pass in isolation).
- `second-brain data-quality phase-08b-gates` exit 1 — `automation_executor.py:1485`.
- `phase-08c-gates` **skipped** (mutates the operator DB).

Evidence: `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`
(`38-cli-and-operator-status.{json,md}`, `phase-09-operator-status.{json,md}`,
`validation-outputs-prompt-38/`).
