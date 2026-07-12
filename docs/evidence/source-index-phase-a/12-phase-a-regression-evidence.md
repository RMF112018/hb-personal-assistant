# A2 corrective — explicit A1 / A3 / A2 / combined regression evidence

All runs at the A2 checkpoint tree `554c4b905a947e7660d2e98fbbd64c9b55b61451` **plus** this corrective's one
added regression test (`test_bootstrap_to_watcher_start_is_non_circular`). Branch
`fix/source-index-phase-a-correctness-trust` off origin/main `9c27839b` (schema V124). Python
`<repo>/.venv` (CPython 3.14.5). Command prefix (from worktree root):
`PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest -p no:cacheprovider`.

Totals are JUnit-XML authoritative (the repo's custom terminal reporter suppresses the per-test tally; the
final summary line is still emitted and quoted).

## Required result: **all Phase A tests introduced through A2 pass — CONFIRMED (0 failures across A1+A3+A2).**

| Regression set | Suite(s) | Tests | Passed | Failed | Summary line |
|---|---|---:|---:|---:|---|
| **A1 — vault deletion-safety** (incl. CLI exclusivity/follow-up) | `test_source_index_vault_deletion_safety.py` | 19 | 19 | 0 | `19 passed in 39.55s` |
| **A3 — canonical mapping** (incl. 4 corrective config-fail-closed tests) | `test_source_root_mapping.py` | 25 | 25 | 0 | `25 passed in 4.39s` |
| **A2 — root trust** (incl. new bootstrap↔watcher non-circular test) | `test_source_root_trust.py` | 36 | 36 | 0 | `36 passed in 56.20s` |
| **Combined cross-checkpoint** (A1+A3+A2 authored + A2 serving/parity) | 5 suites (below) | 114 | 114 | 0 | `114 passed in 179.47s` |

Cross-checkpoint suites: `test_source_index_vault_deletion_safety.py`, `test_source_root_mapping.py`,
`test_source_root_trust.py`, `test_source_connector_service.py`, `test_nas_mcp_source_connector.py`.

## A1 — deletion-safety suite (19) — includes the follow-up
- The A1 follow-up commit `1d58d123` added `test_vault_reconcile_cli_lease_is_os_backed_and_exclusive`
  (OS-backed `fcntl.flock` exclusivity; contention fails closed exit 2). It is present and GREEN in the 19.
- The **broader** A1 regression (the 8 pre-existing suites A1 touches: streaming walk, vault-db reconcile,
  source index, watcher lifecycle/ownership/base, repository) was run **75 passed / 0 failed** at the
  A3-corrective checkpoint (see `09-commit-lineage.md`). Those same watcher/index/reconcile suites reappear
  in the broad-source-index run here with **no new failure** (its only 5 failures are pre-existing baselines
  in OTHER suites — see `10-baseline-reconciliation-matrix.md`).

## A3 — mapping suite (25) — includes the 4 corrective tests
Present and GREEN: `test_health_config_load_failure_fails_closed`,
`test_health_invalid_mapping_config_fails_closed`, `test_valid_empty_config_still_allows_exact_identity_match`,
`test_config_failure_cannot_report_structure_ready` (the A3-corrective fail-closed-config quartet).

## A2 — trust suite (36) — includes the new non-circular regression
Present and GREEN: `test_bootstrap_to_watcher_start_is_non_circular` (added by this corrective; see
`13-watcher-bootstrap-noncircular.md`). The other 35 are the A2-checkpoint trust tests.

## Broader source-index radius (context, not "Phase A introduced")
`a2-validation-broad-source-index.txt`: 261 tests, 256 passed, **5 pre-existing baseline failures** (schema
`==123` trio, structure-cli `78 vs 80`, connector-eval health-description). `a2-validation-client-surface.txt`:
153 tests, 152 passed, **1 pre-existing baseline failure** (`test_output_aliases_defined` `11 vs 10`). All 6
are reconciled in `10-baseline-reconciliation-matrix.md` and reproduce on pristine origin/main. **None is a
Phase A test and none is a Phase A regression.**

## Bottom line
Every test Phase A INTRODUCED through A2 (A1 19 + A3 25 + A2 36, and the 114-test cross-checkpoint superset)
passes with **0 failures**. The only failures anywhere in the wider radius are the 6 disclosed pre-existing
baseline defects, none authored or modified by Phase A.
