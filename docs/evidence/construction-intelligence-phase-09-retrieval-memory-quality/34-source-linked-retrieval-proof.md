# Phase 09 Prompt 34 — Source Linked Retrieval Proof

**Objective:** Prove every retrieval result maps to approved source refs.

- Repo SHA: `e757ef97a1021d173a90bbe4e51888f2540a6f46`
- Schema: **V39** (verified via `construction-agent validate`)
- Package: `1.4.0-phase-09`

## Design — standalone surface, reuse the reserved V38 table (no migration)

New module `src/hb_assistant/construction/second_brain/retrieval/source_linked_proof.py` runs the
hybrid retrieval broker (`build_hybrid_envelope`) and proves every returned result maps to an
approved source ref: a result is **source-linked** iff it carries a non-empty `source_ref` and an
allowlisted `source_family` (not in `retrieval/policy.py` `EXCLUDED_FAMILIES`) — the same rule
`output-eval` (`_source_linked_proof`) uses. No migration, schema stays **V39**, no new table
(`table-inventory` contract count stays **190**); on `--emit-receipt` a metadata-only, guard-clean
summary row persists to the reserved V38 `second_brain_retrieval_source_linked_proof_runs` table
(co-owned with `output-eval`; distinct `slr_` run_id prefix). Read-only by default; makes no
determination.

The contract's required fields (`run_id`, `result_count`, `linked_count`, `unlinked_count`,
`proof_passed`) are emitted in the build/proof JSON. `proof_passed` is true only when
`result_count > 0` and `unlinked_count == 0`.

## Results

- `second-brain retrieval source-linked build --json` (operator DB) → exit 0: `status=source_linked`,
  `result_count=1`, `linked_count=1`, `unlinked_count=0`, `proof_passed=true`, per-family
  `{approved_obsidian_generated_outputs: {linked:1, unlinked:0}}`, `read_only=true`,
  `makes_determination=false`.
- `second-brain retrieval source-linked proof --json` → exit 0: `proof_passed=true` —
  `result_count=3` (deterministic 0 + advisory-semantic 3; the controlled seeded index yields the
  riskier semantic arm), `unlinked_count=0`, `every_result_source_linked=true`,
  `rows_persisted_guard_clean=true`, `read_only_default_no_persist=true`, `no_raw_emitted=true`.
  Wrote `source-linked-retrieval-proof.{json,md}`.
- 6 new tests pass (normal proof / missing-policy fail-closed / stale-schema fail-closed /
  unsafe-source linkage accounting / no-raw-no-writeback proof / guard-clean artifacts).

## Validation matrix

| Check | Result |
| --- | --- |
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | this module clean; only the 2 pre-existing `review_burden_mart.py:165,167` errors remain |
| `pytest tests/test_phase_09_source_linked_retrieval_proof.py` | 6 passed |
| `construction-agent validate --json` | exit 0, 4/4, schema **V39** |
| `data-quality table-inventory --json` | 190 contract / 189 live; unmapped = 3 concurrent `review_burden` tables (not ours) |
| `data-quality no-writeback-proof --json` | exit 0 |
| `second-brain data-quality phase-08a-gates --json` | exit 0 |
| `second-brain data-quality phase-08b-gates --json` | exit 1 — pre-existing `automation_executor.py:1485` AssertionError |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** — mutates operator DB (append-only ledger) |
| `second-brain data-quality phase-08d-gates --json` | exit 0 |
| `second-brain mcp no-raw-access --json` | exit 0 |
| `second-brain mcp no-writeback --json` | exit 0 |
| `pytest tests/test_repo_sensitive_scan.py tests/test_second_brain_no_writeback_proof.py` | pass |

Full captured outputs: `validation-outputs-prompt-34/`.

## Pre-existing (not introduced by this prompt)

- `mypy src`: 2 errors in `review_burden_mart.py:165,167` (concurrent review-burden work).
- `pytest` default-safe subset: `test_v*_table_classified_in_lifecycle_contract` failures (3 unmapped
  `second_brain_review_burden_*` tables) + `test_phase_09_embedding_policy::test_normal_path` (8≠7,
  concurrent Prompt 18/19 vector-loader work). This prompt adds no table and does not touch the
  embedding policy.
- `phase-08b-gates` exit 1 — `automation_executor.py:1485` (pre-existing/environmental).

No stop condition triggered (every retrieval result source-linked; no raw-content persistence, no
writeback, no semantic-retrieval bypass).
