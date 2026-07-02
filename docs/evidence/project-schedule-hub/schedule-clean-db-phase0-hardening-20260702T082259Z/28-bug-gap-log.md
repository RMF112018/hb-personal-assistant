# Bug gap log

## Closed by reconciliation

| ID | Area | Symptom | Resolution | Severity | Blocks full validation |
|----|------|---------|------------|----------|------------------------|
| R1 | Evidence | No `32-final-repo-state.txt` proving final commit | Added post-commit repo-state artifact | P2 | no |
| R2 | Evidence | Missing `11-role-gate-matrix.json` | Role gate tests export structured matrix via `PHASE0_EVIDENCE_DIR` | P2 | no |
| R3 | Tests | Coroutine `RuntimeWarning` in background-worker proofs | Mock `create_task` closes coroutine | P2 | no |
| R4 | Purge | `after_counts` empty despite zero remaining | Explicit zero counts for `before_counts` keys | P2 | no |
| R5 | Evidence | Fixture DB files in evidence directory | Moved to `local-sensitive/`; not tracked | P2 | no |
| R6 | Evidence | `32-final-repo-state.txt` head could not self-reference amend hash | Capture script + `--verify` after final amend | P3 | no |

## Open (monitor in full validation)

| ID | Area | Symptom | Recommended fix | Severity | Blocks full validation |
|----|------|---------|-------------------|----------|------------------------|
| O1 | Role gates | Some viewer PUT routes return 422 not 403 | Confirm route ordering; document as `route_contract_changed` | P3 | no |
| O2 | Purge | `_collect_purge_tables` heuristic is broad | Tighten purge table selection in future pass | P3 | no |
