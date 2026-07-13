# Phase B — Sixth Corrective Audit Response (PB-010: validate the moved claim generation at dispatch entry)

The AEOS review of the fifth round confirmed C6's generic-handler fix (no moved event reaches the unguarded
`complete_event`) and re-affirmed PB-012 FIXED, but held **PB-010 OPEN** for a residual: the moved
**dispatch** branch fabricated the claim generation — `expected_attempt = int(event.get("attempts") or 1)` —
**before** the direct `moved_invalid`, `unconfigured_root`, and `_apply_moved_event` terminalizations, so a
missing/`None`/`0` generation was coerced to attempt 1 and a direct guarded completion could succeed under a
fabricated generation. A second FAIL: the prior "final tree clean" claim was inaccurate.

This work lands as two immutable commits on `phase-b-source-index-architecture-completion`, preserving all
seven prior commits (`80b4d13d`, `e488136f`, `0464e347`, `5aeb7ab3`/C4, `8003ca02`/E5, `3f4a9b2b`/C6,
`6adb9fac`/E7) — no amend:
- **C8** = `9182f3d4` — the code + tests only.
- **E9** = this evidence-only commit, referencing `tested_code_sha = C8`.

**No push / PR / deploy / prod DB / watcher activation / prod migration.**

## FIND-PB-010 residual — generation validated at the dispatch entry, no fabricated attempt

**Fix** (`source_indexer.py`, one module):
- **Validate the claim generation at the moved DISPATCH ENTRY** — before normalization, root lookup,
  dispatch, or any terminalization. No default, no coercion: `type(x) is not int` rejects bool/str; `< 1`
  rejects 0/negative. An invalid generation performs **NO queue mutation** (`continue` → the event is left
  `processing` for `requeue_stuck`). The `int(... or 1)` fallback is **removed**.
- **Extract the C6 backstop into `_terminalize_moved_exception`** (an independent last-resort boundary) so
  the retained trust boundary stays directly testable; the drain delegates to it. Its own generation check
  remains as defense-in-depth. The terminalization exception is bound separately (`terminal_exc`) and only
  safe identifiers are logged (event_id, validated attempt, exception classes) — never messages, paths, root
  keys, or payload.

**Tests** (`tests/test_source_index_moved_drain.py`):
- `test_moved_dispatch_invalid_claim_generation_no_mutation` — the **3×7 matrix**: every invalid generation
  (**missing / None / 0 / negative / nonnumeric string / `True` / `False`**) × every dispatch class
  (**valid_configured / moved_invalid / unconfigured_root**). For every cell: `_apply_moved_event`,
  `complete_owned_event`, and `complete_event` are **all uncalled** (short-circuit at the dispatch entry);
  the **full event row** (`status, attempts, error_code, updated_at, next_attempt_at`) is **byte-identical**
  to the post-claim snapshot (accurate claim: *no post-claim queue mutation*; `claim_queued` already
  legitimately did queued→processing + attempt increment); the pre-indexed source is unchanged, no successor
  lineage, the destination is never indexed / no content invalidation; and deterministic `requeue_stuck`
  recovers.
- `test_terminalize_moved_exception_validates_generation` — direct helper coverage: the seven invalid forms
  call no guarded completion (no fabricated attempt); a valid generation whose guarded completion **raises**
  non-busy is swallowed (event left processing); a valid generation whose completion **succeeds** is called
  cleanly. The superseded backstop-only invalid-generation test is removed. The three existing backstop
  terminalization-failure tests (valid/`moved_invalid`/`unconfigured_root`, attempt=1) still pass and now
  delegate through the helper.

## Worktree-cleanliness remediation (accurate disclosure + isolated proof)
Prior rounds' "final tree clean" claim is corrected. **No tracked source/test drift** is present, but the
main worktree is **not** clean — it carries untracked detached-evidence exports and pre-existing foreign
churn (`docs/implementation/*`, `frontend/*`) that are **not part of the branch**. Merge evidence is produced
from **isolated detached worktrees**:
- **Tested-code proof (C8):** `final-runs/clean-worktree-c8-*.txt` — a detached worktree at C8 with import
  provenance proven **beneath the worktree** (both `hb_assistant` and `construction_financial_review`), a
  clean `git status --short` **before and after** the gate, HEAD == C8, and the isolated gate passing.
- **Final-branch proof (E9):** recorded in the detached manifest — a detached worktree at E9 with a clean
  status, HEAD == E9, `git diff --exit-code C8 E9 -- <source> <test>` = 0 (no code/test diff), and the
  `C8..E9` changed-file list (evidence paths only).
- Temporary worktrees are created and removed under the **explicit operator authorization** granted for this
  round; a `git worktree list --porcelain` inventory is captured **before and after** removal to prove only
  the two newly-created temporaries were removed and no pre-existing worktree or foreign file was touched.

## Validation summary (tested_code_sha = C8 = `9182f3d4`)
- `final-runs/gate-equivalent-c8-9182f3d4.txt` — 30-file de-duplicated gate-equivalent run in the isolated
  C8 worktree, pipefail-correct: `518 passed, 1 warning in 439.03s` (0 failed / 0 errored; the warning is
  the FastAPI/Starlette deprecation), `PYTEST_EXIT=0`. (502 from the fifth round − 6 removed backstop
  params + 22 new C8 tests.)
- `final-runs/ruff-c8.txt` — `RUFF_EXIT=0` on the module + test file.
- `final-runs/mypy-c8.txt` — `MYPY_EXIT=0` on the module.
- `final-runs/c8-no-code-drift.txt` — `DRIFT_DIFF_EXIT=0`.
- `final-runs/clean-worktree-c8-{provenance,status-pre,status-post,head-post}.txt`.

## Commit identity
Recorded in `14-corrective6-committed-tree-identity.md`. E9's own SHA, its patch/bundle checksums, the
post-E9 `git status --short`, the `C8..E9` proof, the E9 final-branch worktree proof, and the worktree
inventory before/after removal live in the **detached manifest** `final-runs/E9-detached-manifest.md`.
