# Phase B — Fifth Corrective Tree Identity (C6 code/tests · PB-010 residual)

Committed-tree identity for the **fifth** corrective code/test commit **C6** on
`phase-b-source-index-architecture-completion`. All prior commits preserved (no amend):
`80b4d13d` → `e488136f` → `0464e347` → `5aeb7ab3` (C4) → `8003ca02` (E5) → **C6**. Evidence lands in the
evidence-only commit **E7** (this file is part of E7). **No push / PR / deploy / prod DB / watcher
activation / prod migration.**

## Non-circular identity
```
tested_code_sha      = 3f4a9b2b084bd720a6f9c8a040b2e7a44cc11707   # C6 — code/tests under test
evidence_parent_sha  = 3f4a9b2b084bd720a6f9c8a040b2e7a44cc11707   # E7's parent == C6
evidence_scope       = evidence-only                             # C6..E7 changes only governed evidence
```
E7's own commit SHA, its patch/bundle checksums, and the **post-E7** `git status --short` are **not**
recorded here (writing them into E7 would change E7 and its SHA — circular). They live in the detached
manifest `final-runs/E7-detached-manifest.md`, produced after E7 exists.

## C6 commit

| Field | Value |
| --- | --- |
| Commit (full) | `3f4a9b2b084bd720a6f9c8a040b2e7a44cc11707` |
| Parent | `8003ca020a874658dfdc8766cfaad1b03942d5d9` (E5) |
| Lineage | `80b4d13d` → `e488136f` → `0464e347` → `5aeb7ab3` (C4) → `8003ca02` (E5) → **C6** |
| Branch | `phase-b-source-index-architecture-completion` |
| Subject | `Phase B 5th corrective (C6/code): moved events never reach the unguarded complete_event fallback (PB-010 residual)` |

## Name-status (`git show --name-status 3f4a9b2b`)
```
M  src/hb_assistant/obsidian_mcp/source_indexer.py
M  tests/test_source_index_moved_drain.py
```
2 files changed, 194 insertions(+), 3 deletions(-). Code + tests only — no evidence, no docs, no governance/
memory. Single structural change (the drain's generic handler at line 2828 becomes moved-aware, fail-closed
on the claim generation).

## No-code-drift proof (tested C6 == worktree at E7 creation)
`final-runs/c6-no-code-drift.txt`:
`git diff --exit-code 3f4a9b2b -- src/hb_assistant/obsidian_mcp/source_indexer.py tests/test_source_index_moved_drain.py`
→ `DRIFT_DIFF_EXIT=0` — the tested source/test files are byte-identical to C6; no uncommitted code change
affected the tested tree.

## C6 patch + bundle (sha256)
```
8c9f72a03750c1ee92cb8d5c68478a84ca2f3b0331b0d3ea43df926f9bfcc6c0  final-runs/phase-b-corrective5-c6-3f4a9b2b.patch
8fae3d100a117eaf6d1bc622304dd66840f6f388685cd36fa8b8c86229579704  final-runs/phase-b-corrective5-c6-3f4a9b2b.bundle
```
- `git format-patch -1 --stdout 3f4a9b2b > final-runs/phase-b-corrective5-c6-3f4a9b2b.patch`
- `git bundle create final-runs/phase-b-corrective5-c6-3f4a9b2b.bundle phase-b-source-index-architecture-completion --not 8003ca02`
- `git bundle verify` → *is okay*; contains ref `3f4a9b2b… refs/heads/phase-b-source-index-architecture-completion`.

## Validation (tested_code_sha = C6)
- `final-runs/gate-equivalent-c6-3f4a9b2b.txt` — 30-file de-duplicated gate-equivalent run under
  `.venv/bin/python -m pytest` (CPython 3.14), pipefail-correct: **`502 passed, 1 warning in 410.83s`**
  (0 failed / 0 errored), **`PYTEST_EXIT=0`**.
  The file records the literal expanded command (no placeholders), `python --version`, and `tested_code_sha`.
- `final-runs/ruff-c6.txt` — `RUFF_EXIT=0` (All checks passed) on the module + the test file.
- `final-runs/mypy-c6.txt` — `MYPY_EXIT=0` (Success, no issues) on the module.
- `final-runs/pre-e7-git-status.txt` — raw pre-E7 `git status --short`.

## Disposition
Merge readiness remains **NO-GO** pending a focused independent PB-010 review of C6, E7, and the detached
manifest. No push, no PR.
