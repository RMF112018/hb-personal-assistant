# A2 corrective — explicit A1 / A3 / A2 / combined regression evidence

All runs at the A2 checkpoint tree `554c4b905a947e7660d2e98fbbd64c9b55b61451` **plus** this corrective's one
added regression test (`test_bootstrap_to_watcher_start_is_non_circular`). Branch
`fix/source-index-phase-a-correctness-trust` off origin/main `9c27839b` (schema V124). Python
`<repo>/.venv` (CPython 3.14.5). Command prefix (from worktree root):
`PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest -p no:cacheprovider`.

Totals are JUnit-XML authoritative (the repo's custom terminal reporter suppresses the per-test tally; the
final summary line is still emitted and quoted).

## Required result: **all Phase A tests introduced through A2 pass — CONFIRMED (0 failures across A1+A3+A2).**

Counts are at **A2 corrective #2** (trust suite grew 36→40: −2 superseded watcher tests, +6 named watcher
lifecycle tests). The combined required-suite run (`corrective2_full`, 15 suites) was **285 tests, 283 passed,
2 failed** — the 2 failures are pre-existing baselines #5/#6 (see `10-baseline-reconciliation-matrix.md`).

| Regression set | Suite(s) | Tests | Passed | Failed | Notes |
|---|---|---:|---:|---:|---|
| **A1 — vault deletion-safety** (incl. CLI exclusivity/follow-up) | `test_source_index_vault_deletion_safety.py` | 19 | 19 | 0 | `19 passed` |
| **A3 — canonical mapping** (incl. 4 corrective config-fail-closed tests) | `test_source_root_mapping.py` | 25 | 25 | 0 | `25 passed` |
| **A2 — root trust** (incl. 6 watcher lifecycle tests) | `test_source_root_trust.py` | 40 | 40 | 0 | `40 passed` |
| **Watcher lifecycle + ownership + automated-refresh** | 4 watch suites | 79 | 79 | 0 | drain-mechanics tests seed real readiness |
| **Manifest + gateway parity + freshness** | parity/freshness/exposure/nas-connector | — | pass | 0 | direct==gateway; freshness guard green |
| **Combined cross-checkpoint** (A1+A3+A2 authored + A2 serving/parity) | 5 suites (below) | 118 | 118 | 0 | `118 passed` |

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

## A2 — trust suite (40) — includes the 6 watcher lifecycle tests
Present and GREEN: `test_watcher_start_before_bootstrap_fails_closed`, `test_bootstrap_succeeds_without_watcher`,
`test_watcher_start_after_bootstrap_succeeds`, `test_watcher_start_blocks_policy_stale`,
`test_watcher_start_blocks_reconciliation_incomplete`, `test_watcher_start_blocks_structure_data_unready`
(see `13-watcher-bootstrap-noncircular.md`). The other 34 are the A2 trust tests.

## Broader source-index radius (context, not "Phase A introduced")
`a2-validation-broad-source-index.txt`: 261 tests, 256 passed, **5 pre-existing baseline failures** (schema
`==123` trio, structure-cli `78 vs 80`, connector-eval health-description) — unaffected by corrective #2.
`a2-validation-client-surface.txt`: 157 tests, 156 passed, **1 pre-existing baseline failure**
(`test_output_aliases_defined` `11 vs 10`). All 6 are reconciled in `10-baseline-reconciliation-matrix.md` and
reproduce on pristine origin/main. **None is a Phase A test and none is a Phase A regression.**

## Bottom line
Every test Phase A INTRODUCED through A2 (A1 19 + A3 25 + A2 40, and the 118-test cross-checkpoint superset)
passes with **0 failures**. The only failures anywhere in the wider radius are the 6 disclosed pre-existing
baseline defects, none authored or modified by Phase A.
