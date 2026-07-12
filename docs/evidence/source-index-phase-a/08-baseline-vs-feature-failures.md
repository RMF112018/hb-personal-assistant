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

## Phase A new failures
None at A0 (A0 commits green; no executable failing tests committed). Per-subphase prove-red node IDs are
enumerated in `07-test-matrix.md` and captured, run, and reported at each sub-phase checkpoint.

## Totals (authoritative, via JUnit XML — the repo's custom terminal reporter suppresses the text tally)
- **294 tests: 291 passed, 3 failed, 0 errors, 0 skipped** across 18 source-index suites (~206s).
- The 3 failures are exactly the stale-assertion trio above; every other source-index test is green on the
  unmodified `origin/main` worktree.
