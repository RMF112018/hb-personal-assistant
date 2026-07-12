# A2 corrective — baseline-failure reconciliation matrix

Purpose: reconcile every failing test node observed anywhere in Phase A validation into ONE table, so the
count is unambiguous. There are **exactly 6 distinct pre-existing baseline failures**. No single validation
run shows all 6 because the 6 nodes are spread across suites and each validation run covers a different
(overlapping) slice. The "how many failures did that run show" question is answered per-run at the bottom.

## Columns
- **Node ID** — the failing test.
- **In A0 baseline set?** — was the node inside the A0 18-suite source-index baseline (`baseline-source-index.txt`)?
- **On pristine origin/main?** — reproduced on a throwaway `git worktree` detached at `9c27839b` with ZERO
  Phase A code (`a2-baseline-recon-originmain.txt`).
- **At A2 HEAD?** — still failing at the A2 checkpoint tree (`554c4b90…` + corrective).
- **Which A2 run shows it** — the validation artifact that includes the node.
- **Same signature everywhere?** — identical assertion/error at A0, pristine origin/main, and A2 HEAD.
- **Classification** — always PRE-EXISTING baseline; never Phase A.

## Matrix

| # | Node ID | In A0 baseline set? | On pristine origin/main? | At A2 HEAD? | Which A2 run shows it | Same signature? | Classification |
|---|---|---|---|---|---|---|---|
| 1 | `test_source_index_metadata_first_bootstrap.py::test_v119_migration_idempotent_and_additive` | YES | YES (`assert 124 == 123`) | YES | broad-source-index | YES (`124 == 123`) | PRE-EXISTING baseline (stale schema literal) |
| 2 | `test_source_index_metadata_generation.py::test_v120_migration_idempotent_and_additive` | YES | YES (`assert 124 == 123`) | YES | broad-source-index | YES (`124 == 123`) | PRE-EXISTING baseline (stale schema literal) |
| 3 | `test_source_index_generation_hardening.py::test_v122_fresh_and_incremental_migration` | YES | YES (`assert 124 == 123`) | YES | broad-source-index | YES (`124 == 123`) | PRE-EXISTING baseline (stale schema literal) |
| 4 | `test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots` | NO (outside A0 18-suite set) | YES (`assert 80 == 78`) | YES | broad-source-index | YES (`80 == 78`) | PRE-EXISTING baseline (stale tool-surface count) |
| 5 | `test_source_index_client_performance_hardening.py::test_output_aliases_defined` | NO (outside A0 18-suite set) | YES (`assert 11 == 10`) | YES | client-surface | YES (`11 == 10`) | PRE-EXISTING baseline (stale output-alias count) |
| 6 | `test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions` | NO (outside A0 18-suite set) | YES (health desc lacks "vault"/"card") | YES | broad-source-index | YES (same assertion on `assistant_source_index_health`) | PRE-EXISTING baseline (health-tool description wording) |

## Why no single run shows "6"
The 6 nodes live in 6 different suites. Each validation run is a deliberate slice:

| Validation run (artifact) | Suites covered | Baseline nodes it contains | Failures shown |
|---|---|---|---|
| `a2-validation-cross-checkpoint.txt` | A1+A3+A2-authored suites only | none | **0** |
| `a2-validation-client-surface.txt` | client trust/serving/manifest surface | #5 only | **1** |
| `a2-validation-broad-source-index.txt` | wide source-index radius | #1, #2, #3, #4, #6 | **5** |
| A0 `baseline-source-index.txt` (origin/main) | A0 18-suite set | #1, #2, #3 | **3** |
| `a2-baseline-recon-originmain.txt` (origin/main, all 6 nodes) | the 6 baseline suites, pristine | #1–#6 | **6** |

`1 (client-surface) + 5 (broad) = 6`, with zero overlap between those two runs and zero baseline nodes in the
cross-checkpoint run. The A0 set of 3 is the subset of #1–#3 that happened to be inside the original 18-suite
baseline; #4/#5/#6 sit in suites the A0 set did not enumerate and were proven pre-existing when they surfaced.

## Definitive pristine reproduction (all 6, one command, zero Phase A code)
A throwaway worktree detached at `origin/main` `9c27839b` (no Phase A branch code) was run against exactly the
6 failing node IDs. Verbatim result in `a2-baseline-recon-originmain.txt`:

```
FFFFFF   [100%]
FAILED tests/test_source_index_metadata_first_bootstrap.py::test_v119_migration_idempotent_and_additive   assert 124 == 123
FAILED tests/test_source_index_metadata_generation.py::test_v120_migration_idempotent_and_additive         assert 124 == 123
FAILED tests/test_source_index_generation_hardening.py::test_v122_fresh_and_incremental_migration           assert 124 == 123
FAILED tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots             assert 80 == 78
FAILED tests/test_source_index_client_performance_hardening.py::test_output_aliases_defined                 assert 11 == 10
FAILED tests/test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions          (health desc)
```

All 6 fail on pristine origin/main with the **same signatures** observed at A2 HEAD → all 6 are PRE-EXISTING
baseline defects, none introduced by Phase A, none absorbed into any prove-red set. Phase A modifies none of
these test files.
