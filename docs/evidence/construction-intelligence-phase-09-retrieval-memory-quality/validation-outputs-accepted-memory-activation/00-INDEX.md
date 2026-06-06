# Validation Outputs — Accepted Memory Activation Addendum Closeout

Captured run of the Prompt-05 validation matrix. Baseline `HEAD = 98ce9694` (parent of the closeout
commit), branch `phase-09-approved-family-coverage-expansion`, schema V39 (no migration).

Proof commands were run with `--no-evidence` so the committed per-proof evidence is not churned — these
files are the closeout-run capture. `llamaindex build --apply` and `approved-sources build` (dry-run by
default) touch only local SQLite/filesystem (no external writeback).

## Toolchain
- `01-git-head.txt`, `01-git-status.txt` — branch + commit + working tree.
- `02-compileall.txt` — `python -m compileall src tests` → **exit 0**.
- `03-ruff.txt` — `ruff check .` → exit 1; **3 pre-existing B008** in `cli/procore.py` (not addendum).
- `04-mypy.txt` — `mypy src` → exit 1; **2 pre-existing errors** in `review_burden_mart.py` (Prompt 34,
  not addendum). The 2 addendum type-casts were fixed in this closeout.
- `05-pytest.txt` — `pytest -m "not live and not integration and not manual"` → **28 failures, all
  pre-existing/environmental** (phase-08b/c/d + 08a-v26 lifecycle-classification drift over the
  unclassified `second_brain_review_burden_*` tables; the 08b data-quality-gate suite; the
  automation-executor service suite, whose failing subset varies run-to-run = environmental). Confirmed
  independent of the addendum by re-running with the closeout edits stashed. Addendum suites are green.

## CLI matrix (one JSON per command)
| File | Command | Result |
|---|---|---|
| 10 | `construction-agent validate` | 4/4 checks ok |
| 11 | `data-quality phase-09-gates` | ok / proof_passed |
| 12 | `data-quality phase-09-operator-status` | exit 0 |
| 13 | `data-quality phase-09-no-writeback-proof` | proof_passed (after closeout `.update()` refactor) |
| 14 | `mcp no-raw-access` | proof_passed |
| 15 | `mcp no-writeback` | proof_passed |
| 20 | `retrieval reader-registry-parity-proof` | parity_ok (10/10) |
| 21 | `retrieval approved-sources build` | status approved (10 families) |
| 22 | `retrieval approved-sources proof` | proof_passed |
| 23 | `retrieval approved-read-model-manifest-proof` | proof_passed |
| 24 | `retrieval read-model-vector-loader-proof` | proof_passed |
| 25 | `retrieval coverage-parity-closeout` | closeout_ok; reader 10/10, manifest 10, **vector 8**, memory `deferred_empty` |
| 26 | `retrieval source-linked build` | exit 0 |
| 27 | `retrieval source-linked proof` | proof_passed |
| 30 | `retrieval llamaindex status` | exit 0 |
| 31 | `retrieval llamaindex build` (dry-run) | exit 0 |
| 32 | `retrieval llamaindex build --apply` | **status applied** (live: 8 families embedded; vectors outside SQLite) |
| 33 | `retrieval llamaindex build-proof` | proof_passed |
| 34 | `retrieval no-raw-vector-index-proof` | proof_passed |
| 40 | `memory candidates build` | exit 0 (read-only) |
| 41 | `memory candidates proof` | proof_passed |
| 42–45 | `memory list --status {accepted,pending_review,rejected,superseded}` | **all count 0 (live corpus empty)** |
| 46 | `memory proof` (acceptance) | proof_passed |
| 47 | `memory quality-controls-proof` | proof_passed |

## Headline
Live accepted-memory corpus is **empty (0)**; live vector-indexed coverage is **8 families** (memory
`deferred_empty`). The 8→9 increase is proven by the Prompt-03 fixture, **not reached live** (no
accepted memory). All guardrail proofs pass. Validation is **not fully clean** (pre-existing failures) →
**not production-ready**.
