# Phase 0 evidence reconciliation

## Why this pass was needed

An evidence review found Phase 0 tooling was largely complete, but the evidence package had gaps:

- No post-commit repo-state artifact proving the actual final commit
- Missing exported `11-role-gate-matrix.json`
- Background-worker test output showed an unawaited coroutine `RuntimeWarning`
- Purge apply proof had empty `after_counts` despite zero remaining records
- Fixture SQLite files existed in the evidence directory (acceptable locally, not for commit)

## What changed

- Role gate tests now export structured matrix JSON to `PHASE0_EVIDENCE_DIR`
- Background-worker tests close coroutines passed to mocked `asyncio.create_task`
- Purge planner `after_counts` now mirrors `before_counts` keys with explicit zero values
- Fixture DB files moved to `local-sensitive/clean-db/phase0-evidence-fixtures/` (git-ignored)
- Evidence artifacts re-run: tests, readiness, artifact scanner, purge apply proof

## Evidence files updated or added

- `11-role-gate-matrix.json` (added)
- `04-background-worker-proof.txt`, `11-role-gate-proof.txt`, `24-focused-tests.txt`
- `10-purge-apply-fixture-proof.json`
- `25-schedule-regression-tests.txt`, `26-frontend-tests.txt`, `schedule-test-manifest.txt`
- `30-phase0-readiness-check.json`, `19-artifact-scanner-proof.json`, `20-artifact-scanner-proof.md`
- `31-evidence-reconciliation.md`, `32-final-repo-state.txt`, `33-background-worker-warning-disposition.md`, `34-fixture-db-artifact-disposition.md`
- `27-phase0-summary.md`, `28-bug-gap-log.md`, `29-operator-decision-log.md`

## Purge after_counts

`10-purge-apply-fixture-proof.json` now includes explicit zero `after_counts` for each table in `before_counts`, e.g. `schedule_file_imports: 0`, while `remaining_tropical_schedule_records` remains `0` and other-project rows survive in the fixture DB.

## Final repo-state artifact (`32-final-repo-state.txt`)

The `head=` field embeds the commit hash inside the same commit object, so it cannot be self-consistent through a normal amend loop. Closeout uses `scripts/dev_schedule_capture_phase0_repo_state.py` to regenerate `32-final-repo-state.txt` after the final amend; verification is `python scripts/dev_schedule_capture_phase0_repo_state.py --evidence-dir ... --verify`.

## Phase 0 readiness

Yes — readiness wrapper reports `ready_for_full_clean_db_validation: true` after reconciliation.
