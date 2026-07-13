# Phase B — Fourth Corrective Tree Identity (C4 code/tests · PB-010 + PB-012)

Committed-tree identity for the **fourth** corrective code/test commit **C4** on
`phase-b-source-index-architecture-completion`. All prior commits are preserved (no amend):
`80b4d13d` → `e488136f` → `0464e347` → **C4**. Evidence lands in a separate evidence-only commit **E5**
(this file is part of E5). **No push / PR / deploy / prod DB / watcher activation / prod migration.**

## Non-circular identity (PLAN-C4R5-003 + C4R6-002)
```
tested_code_sha      = 5aeb7ab39b87600eb0d9e7952eaa3db762c2325b   # C4 — the code/tests under test
evidence_parent_sha  = 5aeb7ab39b87600eb0d9e7952eaa3db762c2325b   # E5's parent == C4
evidence_scope       = evidence-only                             # C4..E5 changes only governed evidence
```
E5's **own** commit SHA and its patch/bundle checksums are **not** recorded here — writing them into E5
would change E5 and its SHA (cryptographically circular). They live in the detached manifest
`final-runs/E5-detached-manifest.md`, produced after E5 exists.

## C4 commit

| Field | Value |
| --- | --- |
| Commit (full) | `5aeb7ab39b87600eb0d9e7952eaa3db762c2325b` |
| Parent | `0464e347d85c762456b7eb607a1d3378ff127b16` |
| Lineage | `80b4d13d` → `e488136f` → `0464e347` → **C4** |
| Branch | `phase-b-source-index-architecture-completion` |
| Subject | `Phase B 4th corrective (C4/code): atomic write-lock ownership + busy-aware fail-closed moved transitions (PB-010)` |

## Name-status (`git show --name-status 5aeb7ab3`)
```
M  src/hb_assistant/obsidian_mcp/source_index_repository.py
M  src/hb_assistant/obsidian_mcp/source_indexer.py
M  tests/test_source_index_moved_drain.py
```
3 files changed, 385 insertions(+), 49 deletions(-). Code + tests only — no evidence, no docs. C4 depends
on no new symbols outside these files (`is_sqlite_busy` is defined in `source_index_repository.py` and
imported by `source_indexer.py`).

## C4 patch + bundle (sha256)
```
cbe4ca1fdd919a20049718e14cf9dbb5385a6531156b8d06d7fc75ebbbee795b  final-runs/phase-b-corrective4-c4-5aeb7ab3.patch
0d032ff61c9038cc5f0046f24e73eb33fda4775e99f84a4bd8f9229fecbc7938  final-runs/phase-b-corrective4-c4-5aeb7ab3.bundle
```
- `git format-patch -1 --stdout 5aeb7ab3 > final-runs/phase-b-corrective4-c4-5aeb7ab3.patch`
- `git bundle create final-runs/phase-b-corrective4-c4-5aeb7ab3.bundle phase-b-source-index-architecture-completion --not 0464e347`
- `git bundle verify` → *is okay*; contains ref `5aeb7ab3… refs/heads/phase-b-source-index-architecture-completion`.

## Validation (tested_code_sha = C4)
- `final-runs/gate-equivalent-c4-5aeb7ab3.txt` — 30-file de-duplicated gate-equivalent run under
  `.venv/bin/python -m pytest` (CPython 3.14), pipefail-correct: **`493 passed, 1 warning in 382.57s`**
  (0 failed / 0 errored; the warning is the FastAPI/Starlette deprecation), **`PYTEST_EXIT=0`**. The file
  records the literal expanded command (no placeholders), `python --version`, and `tested_code_sha`.
- `final-runs/ruff-c4.txt` — `RUFF_EXIT=0` (All checks passed) on the two modules + the test file.
- `final-runs/mypy-c4.txt` — `MYPY_EXIT=0` (Success, no issues) on the two modules.

## Disposition
Merge readiness remains **NO-GO** pending a focused independent PB-010/PB-012 review of C4, E5, and the
detached manifest. No push, no PR.
