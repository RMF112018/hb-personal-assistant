# 01 — Branch and Stack

## Current branch and HEAD

- **Branch:** `docs/schedule-cpm-engine-evaluation-20260628T092114Z`
- **HEAD:** `f2916c21` — `Merge pull request #177 from RMF112018/feat/schedule-cpm-api-frontend-foundation`
- **Position vs `origin/main`:** `0` ahead / `0` behind. This branch points at exactly the
  same commit as `origin/main` / `main`. The evaluation work product (this evidence package)
  is currently **untracked** on top of that commit.

## `git status --short`

See `artifacts/git-status.txt`. Captured state:

```
 M docs/evidence/construction-intelligence-phase-08b-automation-hardening/phase-08b-final-no-writeback-proof.md
 M frontend/src/lib/api.ts
 M frontend/src/pages/SettingsPage.test.tsx
 M frontend/src/pages/SettingsPage.tsx
 M pyproject.toml
 M src/hb_assistant/construction/analytics/api.py
 M tests/test_fastapi_analytics_app_shell.py
?? docs/evidence/schedule-cpm-engine-evaluation/
?? frontend/src/components/settings/ObsidianMcpPanel.tsx
?? src/hb_assistant/obsidian_mcp/
?? tests/test_obsidian_mcp_backend.py
```

### Working-tree note (important for commit scoping)

The working tree was **already dirty before this evaluation work began**, with an unrelated
in-progress feature ("obsidian_mcp" / Settings MCP panel): modified `analytics/api.py`,
`frontend/src/lib/api.ts`, `SettingsPage.*`, `pyproject.toml`, `tests/test_fastapi_analytics_app_shell.py`,
plus untracked `src/hb_assistant/obsidian_mcp/`, `ObsidianMcpPanel.tsx`, and
`tests/test_obsidian_mcp_backend.py`.

These changes are **unrelated to Schedule CPM** and were **not touched** by this evaluation.
The diffs of `analytics/api.py` and `frontend/src/lib/api.ts` were inspected and contain **no
CPM/schedule/longest-path/criticality/DCMA edits** — the CPM API routes are the merged Phase 8
code, unmodified. CPM evidence integrity is therefore unaffected.

**Commit-scope condition:** when authorized, the eventual commit must include **only**
`docs/evidence/schedule-cpm-engine-evaluation/`. It must not capture the obsidian_mcp work.

> **Concurrency note (end of run):** `artifacts/git-status.txt` is the snapshot from the start
> of this run, when the obsidian_mcp work was untracked. **During** this run a concurrent
> obsidian_mcp session **staged** its work into the index (≈25 staged files — backend
> `src/hb_assistant/obsidian_mcp/*`, `analytics/api.py`, frontend Settings panel/api, a new
> `docs/evidence/hb-obsidian-mcp/` package, etc.); see `artifacts/git-status-end.txt`. This
> Schedule-CPM evidence package was added entirely as **untracked** files
> (`?? docs/evidence/schedule-cpm-engine-evaluation/`) and **this run staged nothing**.
>
> Because the index already holds unrelated staged content, a bare `git commit` would commit the
> obsidian_mcp work and **not** this package. To commit only this evidence (when Bobby
> authorizes), use a path-scoped commit that bypasses the dirty index, e.g.:
> `git add docs/evidence/schedule-cpm-engine-evaluation/ && git commit -m "docs(schedule): complete CPM engine evaluation evidence" -- docs/evidence/schedule-cpm-engine-evaluation/`
> Do **not** run `git add -A` / `git commit -a` — that would sweep in the obsidian_mcp changes.

## Recent git graph (CPM phases)

See `artifacts/git-log-cpm-phases.txt` and `artifacts/git-log-stack.txt`. The CPM phase
foundations are **merged to `main`** (not a live stacked branch):

```
f2916c21 Merge PR #177  feat/schedule-cpm-api-frontend-foundation        (Phase 8)
0fa83273 Merge PR #176  feat/schedule-cpm-dcma-critical-path-integration  (Phase 7)
2948b7a8 feat(schedule): surface computed CPM analysis                    (Phase 8 work)
a7930b2d feat(schedule): integrate computed CPM critical path metric      (Phase 7 work)
127f3087 Merge PR #175  feat/schedule-cpm-criticality-foundation          (Phase 6)
1d75011a Merge PR #174  feat/schedule-cpm-longest-path-foundation         (Phase 5)
45e3a64e Merge PR #173  feat/schedule-cpm-float-foundation                (Phase 4)
a056cf7d feat(schedule): add CPM backward pass foundation                 (Phase 3)
404c6b84 feat(schedule): add CPM forward pass foundation                  (Phase 2)
0d927c9e feat(schedule): add CPM graph diagnostics foundation             (Phase 1)
```

## Phases merged to `main`

1. Phase 1 — CPM Graph Diagnostics Foundation
2. Phase 2 — CPM Forward Pass Foundation
3. Phase 3 — CPM Backward Pass Foundation
4. Phase 4 — CPM Float Foundation
5. Phase 5 — CPM Longest Path Foundation
6. Phase 6 — Critical / Near-Critical Foundation
7. Phase 7 — DCMA Critical Path Metric Integration (schema v89)
8. Phase 8 — CPM API / Frontend Surfacing Foundation (no schema change)

Because Phases 1–8 are merged, `git diff --name-only origin/main...HEAD` is **empty** (see
`artifacts/changed-files-since-phase1.txt`); the phase commit history above is the authoritative
record of the CPM file additions.
