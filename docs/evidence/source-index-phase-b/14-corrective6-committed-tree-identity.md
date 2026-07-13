# Phase B — Sixth Corrective Tree Identity (C8 code/tests · PB-010 dispatch generation)

Committed-tree identity for the **sixth** corrective code/test commit **C8** on
`phase-b-source-index-architecture-completion`. All prior commits preserved (no amend):
`80b4d13d` → `e488136f` → `0464e347` → `5aeb7ab3` (C4) → `8003ca02` (E5) → `3f4a9b2b` (C6) → `6adb9fac`
(E7) → **C8**. Evidence lands in the evidence-only commit **E9** (this file is part of E9). **No push / PR /
deploy / prod DB / watcher activation / prod migration.**

## Non-circular identity
```
tested_code_sha      = 9182f3d488b737b74bf0447b77cf25b445047d54   # C8 — code/tests under test
evidence_parent_sha  = 9182f3d488b737b74bf0447b77cf25b445047d54   # E9's parent == C8
evidence_scope       = evidence-only                             # C8..E9 changes only governed evidence
```
E9's own commit SHA, its patch/bundle checksums, the post-E9 `git status --short`, the E9 final-branch
worktree proof, and the worktree inventory before/after removal are **not** recorded here (they would change
E9 and its SHA — circular). They live in the detached manifest `final-runs/E9-detached-manifest.md`.

## C8 commit

| Field | Value |
| --- | --- |
| Commit (full) | `9182f3d488b737b74bf0447b77cf25b445047d54` |
| Parent | `6adb9fac90129ab4eb813110cd79918274285be1` (E7) |
| Lineage | `80b4d13d` → `e488136f` → `0464e347` → `5aeb7ab3` → `8003ca02` → `3f4a9b2b` → `6adb9fac` → **C8** |
| Branch | `phase-b-source-index-architecture-completion` |
| Subject | `Phase B 6th corrective (C8/code): validate moved claim generation at dispatch entry, no fabricated attempt (PB-010 residual)` |

## Name-status (`git show --name-status 9182f3d4`)
```
M  src/hb_assistant/obsidian_mcp/source_indexer.py
M  tests/test_source_index_moved_drain.py
```
2 files changed, 142 insertions(+), 52 deletions(-). Code + tests only — no evidence, no docs, no
governance/memory. Two edits in one module: (1) validate the claim generation at the moved dispatch entry
(remove `or 1`); (2) extract the C6 backstop into `_terminalize_moved_exception` (independent boundary) and
delegate.

## No-code-drift proof (tested C8 == worktree at E9 creation)
`final-runs/c8-no-code-drift.txt`:
`git diff --exit-code 9182f3d4 -- src/hb_assistant/obsidian_mcp/source_indexer.py tests/test_source_index_moved_drain.py`
→ `DRIFT_DIFF_EXIT=0`.

## C8 patch + bundle (sha256)
```
e146fd00101eed6e06199fb2ca3645a6c692b665f212c6ac7fcbfde1b3741c60  final-runs/phase-b-corrective6-c8-9182f3d4.patch
809b3fb7bc48215ed9ef09c6b1cce0b8e83b0b826041e5bd064bd513d52d5f4b  final-runs/phase-b-corrective6-c8-9182f3d4.bundle
```
- `git format-patch -1 --stdout 9182f3d4 > final-runs/phase-b-corrective6-c8-9182f3d4.patch`
- `git bundle create final-runs/phase-b-corrective6-c8-9182f3d4.bundle phase-b-source-index-architecture-completion --not 6adb9fac`
- `git bundle verify` → *is okay*.

## Validation (tested_code_sha = C8)
- `final-runs/gate-equivalent-c8-9182f3d4.txt` — 30-file de-duplicated gate-equivalent run in the **isolated
  clean C8 worktree** under `.venv/bin/python -m pytest` (CPython 3.14), pipefail-correct: **`518 passed, 1
  warning in 439.03s`** (0 failed / 0 errored), **`PYTEST_EXIT=0`**. Literal expanded command, `python
  --version`, `tested_code_sha`, and the isolated worktree path recorded in-file; isolated status clean
  before AND after the gate; HEAD == C8 post-gate.
- `final-runs/clean-worktree-c8-provenance.txt` — import origins for `hb_assistant` and
  `construction_financial_review` proven **beneath the C8 worktree** (not the main checkout).
- `final-runs/clean-worktree-c8-status-pre.txt` / `-status-post.txt` — the isolated checkout is clean
  **before and after** the gate; `-head-post.txt` — HEAD still == C8.
- `final-runs/ruff-c8.txt` (`RUFF_EXIT=0`), `final-runs/mypy-c8.txt` (`MYPY_EXIT=0`),
  `final-runs/c8-no-code-drift.txt` (`DRIFT_DIFF_EXIT=0`).

## Disposition
Merge readiness remains **NO-GO** pending a focused independent PB-010 review of C8, E9, and the detached
manifest. No push, no PR.
