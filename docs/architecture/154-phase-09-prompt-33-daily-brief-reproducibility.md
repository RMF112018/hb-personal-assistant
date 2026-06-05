# 154 — Phase 09 Prompt 33: Daily Brief Reproducibility

## Context

Phase 09 Prompt 33. **Objective:** *Prove daily brief reproducibility with controlled inputs and
source refs.*

The Phase 08A daily brief generator (`construction/second_brain/daily_brief/`) is deterministic by
construction: `run_daily_brief()` assembles a bounded, source-linked context, renders redacted
markdown **from cards** (never from model text), and computes a SHA256 `output_path_hash`. What did
not yet exist was an evidence-backed proof that *identical controlled inputs produce an identical
output hash with preserved source refs* — and that this holds with no raw content, no external
writeback, and no determination. This prompt adds that proof surface.

## Decision — proof-only, no schema change

No new migration, no schema bump (stays at **V39**), and no operator-DB writes. This mirrors the
existing `build_daily_brief_agent_proof()` (which persists nothing) and avoids migrator
merge-conflict risk with the other Phase 09 prompts committing concurrently on `main`. The
contract's required fields (`date`, `input_snapshot_hash`, `output_hash`, `source_refs`,
`evaluation_receipt_id`) and the 23 guard attestations are emitted as **metadata-only** values in
the build/proof JSON, not as new SQLite columns. The reproducibility experiment runs entirely in
throwaway temp DBs + temp vaults; the operator DB is only opened **read-only** for the fail-closed
schema-readiness gate.

## Design

New module `construction/second_brain/daily_brief_reproducibility.py`, replicating the established
Phase 09 advisory/proof skeleton (Prompt 32 `agent_performance_feedback.py`):

- **`build_daily_brief_reproducibility(db_path=None, *, brief_date=None, project_key=None)`** —
  fail-closed loads the contract + seed, gates on `_schema_ready` (>= V39 with `daily_brief_runs`),
  then runs the Phase 08A generator **twice** over the identical seeded controlled inputs (one
  cross-source relationship + one project-issue-history item; reusing the
  `build_daily_brief_agent_proof` seeding pattern), each in its own temp DB + temp vault with the
  mock adapter and `mode="apply"`. It compares the two runs and emits metadata-only:
  `input_snapshot_hash` (SHA256 over the canonical controlled-input descriptor), `output_hash` /
  `output_hash_b` / `output_hash_match`, `source_refs` (aggregated to `{source_family, count}` —
  never raw record refs), `source_refs_match`, `evaluation_receipt_id` (the brief's
  `evaluation_run_id`) / `evaluation_receipt_present`, `review_tier`, `degradation_mode`,
  `reproducible`, and a compact `guard_attestation` (`{all_false: true, column_count: 23}`).
- **`build_daily_brief_reproducibility_proof(*, db_path=None, evidence_dir=None, write_evidence=True)`**
  — runs the build against a throwaway migrated temp DB (when `db_path is None`) and asserts:
  `output_hash_match`, non-empty `output_hash`, `source_refs_preserved` (matching family counts,
  count > 0), `evaluation_receipt_present`, `makes_determination is False`, `guards_zero` (all 23
  guard columns attested false), and `no_raw_emitted`. Writes guard-clean JSON + MD evidence via the
  shared `_assert_no_raw` scanner.
- Custom `DailyBriefReproducibilityError` (fail-closed); contract registered with one line in
  `contracts.PHASE_09_CONTRACT_FILES`.

CLI: `second-brain daily-brief-reproducibility build|proof --json` (exit 0 success, 3 fail-closed).

### Why `source_refs` is aggregated to family counts

The contract requires a `source_refs` field, but emitting individual record refs risks leaking
metadata that varies per record. Aggregating to a sorted `{source_family: count}` map proves
source-ref **preservation** across the two runs while keeping the surface strictly metadata-only and
trivially guard-clean. The 23 guard column *names* are likewise not echoed (they contain `raw_*`
substrings that would trip naive no-raw scanners); they are attested in aggregate via
`guard_attestation`.

## Validation

Schema V39; `construction-agent validate` 4/4; `table-inventory` **190 contract / 189 live,
unchanged** (this prompt adds no table — `in_db_not_in_contract` is exactly the three concurrent
`second_brain_review_burden_*` tables, not ours). New surface: `build` → `reproducible=true`,
`output_hash_match=true`, `read_only=true`; `proof` → `proof_passed=true` (all sub-checks true,
deterministic `output_hash`). 6 new tests (normal / missing-policy / stale-schema / no-raw /
no-raw-no-writeback proof / guard-clean artifacts). compileall exit 0; ruff clean; `mypy src` clean
for this module (only the 2 pre-existing `review_burden_mart.py` errors remain).

### Pre-existing, not introduced by this prompt

- `mypy src`: 2 errors in `review_burden_mart.py:165,167` (concurrent review-burden work).
- `pytest` default-safe subset: the `test_v*_table_classified_in_lifecycle_contract` failures +
  the 3 unmapped `second_brain_review_burden_*` tables (concurrent review-burden work).
- `second-brain data-quality phase-08b-gates` exit 1 — `automation_executor.py:1485`
  `build_automation_execution_proof` AssertionError (pre-existing/environmental).
- `phase-08c-gates` was **skipped** (mutates the operator DB — append-only ledger).

Evidence: `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`
(`33-daily-brief-reproducibility.{json,md}`, `daily-brief-reproducibility-proof.{json,md}`,
`validation-outputs-prompt-33/`).
