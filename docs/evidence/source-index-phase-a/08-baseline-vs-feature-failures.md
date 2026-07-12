# A0 — Baseline vs Feature Failures

Run on the fresh `origin/main` (`9c27839b`) worktree **before any Phase A edit**.
Command (from worktree root):
```
PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest -p no:cacheprovider -q \
  <18 source-index suites — see 01-repo-truth-baseline.md / baseline-source-index.txt>
```
Raw output: `baseline-source-index.txt`. `PYTEST_EXIT=1` (solely due to the 3 known baseline failures below).

## Known baseline failures (PRE-EXISTING; NOT Phase A; never absorbed into a prove-red set)
All three are **stale test assertions**, not runtime defects. Each hard-codes the schema version as `123`, but
`origin/main` correctly advanced `LATEST_SCHEMA_VERSION = 124` (V124 FTS join index, PR #303/#304) without
updating these chained-equality assertions. The migrator returns the correct `124`; the assertion `124 == 123`
fails.

| Node ID | Assertion | Cause |
|---|---|---|
| `tests/test_source_index_generation_hardening.py::test_v122_fresh_and_incremental_migration` | `apply() == LATEST_SCHEMA_VERSION == 123` (line 977) | stale `== 123`; actual 124 |
| `tests/test_source_index_metadata_first_bootstrap.py::test_v119_migration_idempotent_and_additive` | `v1 == v2 == 123` (line 503) | stale `== 123`; actual 124 |
| `tests/test_source_index_metadata_generation.py::test_v120_migration_idempotent_and_additive` | `v1 == v2 == 123` (line 56) | stale `== 123`; actual 124 |

**Disposition:** out of Phase A scope (unrelated stale assertions predating this branch). Phase A does **not**
modify them. Note for A4: A4 bumps `LATEST_SCHEMA_VERSION=125`; these three will continue to fail on `== 123`
and remain classified as pre-existing baseline failures. A4's own migration evidence uses fresh, correct
assertions. (If the maintainers wish, a separate trivial PR can refresh these `== 123` literals to `LATEST_SCHEMA_VERSION`.)

## Known baseline failure #4 (discovered during A3 validation; PRE-EXISTING; NOT Phase A)
The A3 validation set includes `tests/test_source_structure_cli.py`, which was **not** part of the A0 18-suite
source-index baseline set above, so this failure surfaced for the first time during A3. It is another **stale
test assertion**, not a runtime defect:

| Node ID | Assertion | Cause |
|---|---|---|
| `tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots` | `gate_off["summary"]["expected_exposed"] == 78` (line 106) | stale hard-coded MCP tool-surface count; actual exposed count is `80` |

**Proof it is pre-existing, not caused by Phase A:**
1. Phase A (A1+A3) adds **zero** MCP tools — it touches vault-deletion safety and root-mapping resolution only,
   no `tool_registration`/manifest surface.
2. Reverting all Phase A `src` edits to `origin/main` state still reproduces `assert 80 == 78`.
3. **Definitive:** the test was run on a throwaway, fully pristine `git worktree` detached at `origin/main`
   (`9c27839b`) with no Phase A code present — it fails identically with `assert 80 == 78`.

This is exactly analogous to the stale `== 123` schema-version trio: a hard-coded expected count (`78`) that was
not updated when the tool surface grew to `80` upstream. It is disclosed here and **never absorbed into the A3
prove-red set**. Phase A does not modify it. (A separate trivial PR can refresh the `78`/`85` literals.)

## Known baseline failures #5 and #6 (discovered during A2 validation; PRE-EXISTING; NOT Phase A)
The A2 validation set includes two suites outside the A0 18-suite set, each surfacing another **stale
assertion**, both reproduced on a pristine `origin/main` (`9c27839b`) worktree with zero Phase A code:

| Node ID | Assertion | Cause |
|---|---|---|
| `tests/test_source_index_client_performance_hardening.py::test_output_aliases_defined` | `len(ASSISTANT_OUTPUT_ALIASES) == len(ALL_PA_OUTPUT_TOOLS) == 10` (line 235) | stale hard-coded output-alias count; actual is `11` |
| `tests/test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions` | each source tool's description contains `"vault"`/`"card"` (line 99) | `assistant_source_index_health`'s description contains neither |

**Proof they are pre-existing, not caused by A2:**
1. `test_output_aliases_defined` counts MCP output-tool aliases — A2 adds no output tools; it fails
   identically (`11 == 10`) on pristine `origin/main`.
2. `test_all_source_tools_have_disambiguating_descriptions` fails on **`assistant_source_index_health`**, not
   on `assistant_get_source` (the only tool docstring A2 changed — and that docstring still contains
   "...its card linkage..."). It fails identically on pristine `origin/main`.

Both are disclosed here and **never absorbed into the A2 prove-red set**. Phase A does not modify them.

## Phase A new failures
None. Every sub-phase (A1, A3, A2) commits GREEN; the branch has no committed failing tests. Per-subphase
prove-red output lives in the evidence package (`a1-prove-red.txt`, `a3-prove-red.txt`, `a2-prove-red.txt`).

## Totals (authoritative, via JUnit XML — the repo's custom terminal reporter suppresses the text tally)
- **294 tests: 291 passed, 3 failed, 0 errors, 0 skipped** across 18 source-index suites (~206s).
- The 3 failures are exactly the stale-assertion trio above; every other source-index test is green on the
  unmodified `origin/main` worktree.
