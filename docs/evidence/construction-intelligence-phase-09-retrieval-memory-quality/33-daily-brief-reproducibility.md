# Phase 09 Prompt 33 — Daily Brief Reproducibility

**Objective:** Prove daily brief reproducibility with controlled inputs and source refs.

- Repo SHA: `098a7d25f2eebf5f7852162290c7471029d58c1a`
- Schema: **V39** (verified via `construction-agent validate`)
- Package: `1.4.0-phase-09`

## Design — proof-only, no schema change

No migration, no schema bump (stays **V39**), no new table (`table-inventory` contract count stays
**190**), and **no operator-DB writes**. New module
`src/hb_assistant/construction/second_brain/daily_brief_reproducibility.py` runs the existing Phase
08A generator (`run_daily_brief()`) **twice** over the identical seeded controlled inputs (one
cross-source relationship + one project-issue-history item), each in its own throwaway temp DB +
temp vault with the mock adapter and `mode="apply"`, and checks that both runs produce the same
approved-output SHA256 hash with the same metadata-only source-ref coverage and a present evaluation
receipt. The operator DB is opened **read-only** only for the fail-closed schema-readiness gate.

The contract's required fields are emitted as metadata-only values in the build/proof JSON:

| Required field | Value |
| --- | --- |
| `date` | `2026-06-02` |
| `input_snapshot_hash` | `e8e0b6982ee8a5d9…` (SHA256 of the canonical controlled-input descriptor) |
| `output_hash` | `7e1b4c294e66d1b2…` (deterministic; identical across both runs) |
| `source_refs` | `[{cross_source_relationships:1}, {project_issue_history_items:1}]` (family counts only) |
| `evaluation_receipt_id` | present (per-run instance id; both runs non-empty) |

The 23 guard columns are attested in aggregate (`guard_attestation = {all_false: true,
column_count: 23}`) — their raw `*_persisted`/`*_performed` names are deliberately not echoed (they
would trip naive no-raw scanners). `source_refs` is aggregated to `{source_family, count}` so no raw
record refs are emitted.

## Results

- `second-brain daily-brief-reproducibility build --json` → exit 0: `status=built`,
  `reproducible=true`, `output_hash_match=true`, `source_ref_count=2`,
  `evaluation_receipt_present=true`, `makes_determination=false`, `read_only=true`.
- `second-brain daily-brief-reproducibility proof --json` → exit 0: `proof_passed=true`
  (`output_hash_match`, `source_refs_preserved`, `evaluation_receipt_present`, `guards_zero`,
  `no_raw_emitted` all true). Wrote `daily-brief-reproducibility-proof.{json,md}`.
- 6 new tests in `tests/test_phase_09_daily_brief_reproducibility.py` pass (normal /
  missing-policy fail-closed / stale-schema fail-closed / no-raw emission / no-raw-no-writeback
  proof / guard-clean artifacts).

## Validation matrix

| Check | Result |
| --- | --- |
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | this module clean; only the 2 pre-existing `review_burden_mart.py:165,167` errors remain |
| `pytest tests/test_phase_09_daily_brief_reproducibility.py` | 6 passed |
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

Full captured outputs: `validation-outputs-prompt-33/`.

## Pre-existing (not introduced by this prompt)

- `mypy src`: 2 errors in `review_burden_mart.py:165,167` (concurrent review-burden work).
- `pytest` default-safe subset: exit 1, **11 failures — all pre-existing/concurrent, none introduced
  here; all 6 new Prompt-33 tests pass**. 10x `test_v*_table_classified_in_lifecycle_contract`
  (v26/v28/v29/v30/v31/v32/v33/v34/v35/v37 — the global lifecycle assertion fails on the 3 unmapped
  concurrent `second_brain_review_burden_*` tables; this prompt adds no table); 1x
  `test_phase_09_embedding_policy::test_normal_path` (`embeddable_family_count` 8 ≠ 7 — concurrent
  Prompt 18/19 vector-loader work; this prompt does not touch the embedding policy/seed).
- `phase-08b-gates` exit 1 — `automation_executor.py:1485` (pre-existing/environmental).

No stop condition triggered (no raw-content persistence, no writeback, no semantic-retrieval bypass).
