# Phase A — commit lineage (through A3)

All commits are local on branch `fix/source-index-phase-a-correctness-trust`, branched from
`origin/main` `9c27839b48fdab0e882fa475a6ace81dc93762fd`. No push / PR / merge / force.

| Order | Full SHA | Checkpoint |
|---|---|---|
| 1 | `963c1759…` | A0 — repo-truth baseline, audit, test-design matrix (GREEN) |
| 2 | `e1a333ec16e4c10ed8dc901af977e0879918f3c2` | A1 — vault deletion-safety gate (GREEN) |
| 3 | `1d58d123a3b58463eecb270609d6afba69ed4609` | A1 follow-up (GREEN) — see below |
| 4 | `80d089eea96a07016babaab852d67a3fc2355991` | A3 — canonical structure-root mapping (GREEN) |
| 5 | `073a3a71a8a338b2bc1c55d7943a32e3dda5566a` | A3 corrective — fail-closed config loading + evidence split (GREEN) |
| 6 | `554c4b905a947e7660d2e98fbbd64c9b55b61451` | A2 — root-specific client trust, fail-closed only (GREEN) |
| 7 | `351c7e4c…` | A2 corrective #1 — evidence correction + 1 non-circularity regression test (GREEN) |
| 8 | *(branch HEAD — this A2-corrective-#2 commit)* | A2 corrective #2 — watcher trust enforcement + client read contract (GREEN) |

## A2 corrective #2 (commit 8) — scope
Two implementation-contract fixes on the HOLD-A4 disposition (see `14-a2-corrective2-watcher-and-read-contract.md`):
- **Watcher startup fails closed** for a not-ready required root via the new shared-authority field
  `safe_for_watcher_activation` (bootstrapped + certified + reconciled + structure-data-ready); non-circular
  (bootstrap is watcher-independent). +6 named watcher lifecycle tests (trust suite 36→40); 4 existing
  drain-mechanics tests aligned to seed real readiness.
- **Client-visible `assistant_source_file_read` purpose corrected** in `tool_entry_manifest.py` (bounded
  excerpt / no complete-file / safe root / truncation-fallback). `semantic_surface_checksum`
  `…c4bf09fc`→`…a53b72` (regenerated, one purpose only).
- Src: `source_root_trust.py`, `source_watch.py`, `tool_entry_manifest.py`. Evidence: `04`, `09`, `11`, `13`,
  `14` + `manifest-checksum-a2corrective2.txt`. No push/PR/merge/force; no production mutation; tool names preserved.

## A2 corrective follow-up (commit 7) — scope

Authorized narrow evidence correction on the HOLD-A4 disposition. Changes:
- **Renamed/replaced** the internally-inconsistent `a2-validation-{focused,superset}.txt` with three
  correctly-scoped artifacts: `a2-validation-cross-checkpoint.txt` (114/114), `a2-validation-client-surface.txt`
  (153, 152 pass / 1 baseline), `a2-validation-broad-source-index.txt` (261, 256 pass / 5 baseline), each with
  exact command, base SHA, JUnit totals, failing node IDs, and A0 comparison.
- **Added** `10-baseline-reconciliation-matrix.md` (6 baseline nodes × A0/pristine/HEAD/run/signature/class),
  `11-manifest-semantic-diff.md` (identical regenerated checksum + no `purpose` drift + probe artifacts),
  `12-phase-a-regression-evidence.md` (explicit A1 19 / A3 25 / A2 36 / cross 114 counts),
  `13-watcher-bootstrap-noncircular.md` (call flow + real-`bootstrap()` regression test).
- **Added one test** `tests/test_source_root_trust.py::test_bootstrap_to_watcher_start_is_non_circular`
  (drives the real `source_bootstrap.bootstrap()`; proves the non-circular bootstrap→watcher sequence). This is
  the only source-of-truth/test change; all other changes are evidence-only. Branch stays GREEN.
- No push / PR / merge / force. No production mutation. No new tool/write surface.

## Intervening commit `1d58d123` — full disclosure

- **Full SHA:** `1d58d123a3b58463eecb270609d6afba69ed4609`
- **Subject:** `A1 follow-up: fix double-close in vault-reconcile lease + assert OS-backed exclusivity`
- **Committed:** 2026-07-12 06:03 −0400, **before A3 began** (A3 = `80d089ee` used it as parent).
- **Why it was needed:** The A3 authorization message required preserving a test or implementation assertion
  that the recovery lease is an **OS-backed** file lock (`fcntl.flock`) shared across independent processes,
  not an in-memory mutex. Writing that exclusivity test surfaced a **real bug** in the A1 code.

### `git show --stat 1d58d123`
```
 src/hb_assistant/cli/source_watch.py             |  2 +-
 tests/test_source_index_vault_deletion_safety.py | 29 ++++++++++++++++++++++++
 2 files changed, 30 insertions(+), 1 deletion(-)
```

### Files changed & semantic summary
1. **`src/hb_assistant/cli/source_watch.py`** (1 line) — In the `vault-reconcile` lease-contention branch,
   removed a redundant inner `os.close(lock_fd)`. On contention the fd was closed in the `except` branch AND
   again in the `finally` clause; the second `os.close` raised `Bad file descriptor`, which masked the
   intended `typer.Exit(2)` and caused the command to exit **1** instead of **2**. The `finally` clause now
   owns the single close, so contention **fails closed with exit 2** as designed.
2. **`tests/test_source_index_vault_deletion_safety.py`** (+29) — Added
   `test_vault_reconcile_cli_lease_is_os_backed_and_exclusive`: holds an `fcntl.flock` on the lease path via a
   **separate fd**, then asserts the command's non-blocking acquisition fails closed (exit 2, "holds the local
   lease"). This proves the lease is OS-backed and exclusive, and is the regression test for the bug above.

### Did it modify A1 runtime behavior? — YES (narrow, disclosed)
It changed one runtime behavior: **the `vault-reconcile` exit code on lease contention (1 → 2)**. This is a
strict correctness improvement (fail-closed exit-code fidelity) confined to the contention path. It did **not**
change deletion-safety logic, the completeness gate, the empty-root guard, or the transactional reconcile.

### Complete A1 regression suite after `1d58d123` (re-run at the A3 corrective checkpoint)
Because `1d58d123` altered A1 runtime behavior, the complete A1 suite was re-run:
```
PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/test_source_index_vault_deletion_safety.py \
  tests/test_source_index_streaming_walk.py \
  tests/test_obsidian_vault_db_reconcile.py \
  tests/test_obsidian_source_index.py \
  tests/test_obsidian_source_watch.py \
  tests/test_obsidian_source_watch_lifecycle.py \
  tests/test_obsidian_source_watch_ownership.py \
  tests/test_source_index_repository.py
```
**Result: 75 tests, 75 passed, 0 failed, 0 errors** (exit 0). No A1 regression; the OS-backed exclusivity
test passes and the contention path returns exit 2.
