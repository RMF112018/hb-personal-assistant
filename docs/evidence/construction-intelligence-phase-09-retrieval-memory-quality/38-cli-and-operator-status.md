# Phase 09 Prompt 38 — CLI and Operator Status

**Objective:** Expose repo-consistent CLI status/eval/build/proof surfaces.

- Repo SHA: `d518db951218fa2e0d407b739089188a5c894b1d`
- Schema: **V39** (verified via `construction-agent validate`)
- Package: `1.4.0-phase-09`

## Design — read-only operator-status aggregator, no migration

New module `src/hb_assistant/construction/second_brain/phase_09_operator_status.py` adds
`second-brain data-quality phase-09-operator-status` — a single repo-consistent view of every Phase-09
CLI surface. No migration (schema stays **V39**), no new table (`table-inventory` count stays **190**),
read-only (persists nothing; re-runs no heavy forensic proofs).

It is driven by a **surface registry** (`resources/config/phase_09_operator_status.seed.yaml`) that
mirrors the repo's actual CLI command set. For each surface it reports `name`, `cli_path`, `kinds`
(status/build/proof/eval/gates/apply/search/run), `contract_present`, and owning-table `row_count`. It
rolls up the read-only `build_phase_09_schema_status_report` (`schema_ready` = schema present + all 22
tables + 23 guards — deliberately **not** requiring all-rows-zero, so a populated table does not fail
the status) and `build_phase_09_gates_proof` (`gates_ok`) into an honest `overall_status`
(`advisory_ready` when schema_ready ∧ gates_ok ∧ all_contracts_present, else `degraded`/`not_ready`).
**Readiness is never overstated** — an empty-substrate surface is `advisory_ready`, never operational.

## Results

- `second-brain data-quality phase-09-operator-status --json` (live operator DB) → exit 0:
  `overall_status=advisory_ready`, `operator_status_ok=true`, **24 surfaces** (7 status / 14 build / 22
  proof / 1 gates), `schema_ready=true`, `gates_ok=true`, `all_contracts_present=true`,
  `readiness_overstated=false`. Wrote `phase-09-operator-status.{json,md}`.
- Sample Phase-09 surface commands (`retrieval llamaindex/embedding-policy/hybrid status --json`)
  execute exit 0 — confirming the repo-consistent command set.
- 6 new tests pass (normal / missing-policy fail-closed / stale-schema fail-closed / unsafe-source
  missing-contract not-overstated / no-raw-no-determination / guard-clean artifacts).

## Validation matrix

| Check | Result |
| --- | --- |
| `compileall src tests` | exit 0 |
| `ruff check .` | exit 1 — **3 B008 in `cli/procore.py` only** (not mine; my files ruff-clean) |
| `mypy src` | this module clean; only the 2 pre-existing `review_burden_mart.py` errors remain |
| `pytest tests/test_phase_09_operator_status.py` | 6 passed |
| `construction-agent validate --json` | exit 0, 4/4, schema **V39** |
| `data-quality table-inventory --json` | 190 contract / 189 live; unmapped = 3 concurrent `review_burden` tables |
| `data-quality no-writeback-proof --json` | exit 0 |
| `second-brain data-quality phase-08a-gates --json` | exit 0 |
| `second-brain data-quality phase-08b-gates --json` | exit 1 — pre-existing `automation_executor.py:1485` |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** — mutates operator DB |
| `second-brain data-quality phase-08d-gates --json` | exit 0 |
| `second-brain data-quality phase-09-gates --json` | exit 0 |
| `second-brain data-quality phase-09-no-writeback-proof --json` | exit 0 |
| `second-brain mcp no-raw-access / no-writeback --json` | exit 0 |
| `pytest tests/test_repo_sensitive_scan.py tests/test_second_brain_no_writeback_proof.py` | pass |

Full captured outputs: `validation-outputs-prompt-38/`.

## Pre-existing (not introduced by this prompt)

- `ruff check .`: 3 B008 in `cli/procore.py` (my files clean).
- `mypy src`: 2 errors in `review_burden_mart.py` (concurrent review-burden work).
- `pytest` default-safe subset: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7) +
  ~21 full-suite test-ordering `daily_brief_*`/`agent_receipts` failures (all pass in isolation).
- `phase-08b-gates` exit 1 — `automation_executor.py:1485` (pre-existing/environmental).

No stop condition triggered (no readiness overstatement, no raw-content persistence, no writeback, no
missing contract reported as present).
