# 00 Preflight — Prompt 16 Route/API Contract Hardening

Date: 2026-06-07
Branch: main
HEAD: be470af1326c82b4c78be6103969e6a0622067be

## Baseline Commands Executed

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were run (with venv python prefix correction for python -m invocations, as required by CLAUDE.md workspace rules; bare `python` was not on PATH in the execution shell).

Full captured output (abridged for the python venv runs; git/node/npm verbatim):

```
=== GIT STATUS SHORT ===
 M docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/coverage-parity-closeout.json
 M docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/coverage-parity-closeout.md
 M docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/no-raw-vector-index-proof.json
 M docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/no-raw-vector-index-proof.md
?? .claude/
?? .code-graph/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? package-lock.json
?? src/hb_assistant/source_refresh/
=== BRANCH ===
main
=== HEAD ===
be470af1326c82b4c78be6103969e6a0622067be
=== GIT LOG ONELINE -n 30 ===
be470af1 chore(scripts): add local MCP stdio launcher for second-brain integration
... (prior commits; HEAD is the audit baseline)
=== PIP SHOW FASTAPI (venv) ===
Name: fastapi
Version: 0.136.3
...
=== PYTEST VERSION (venv) ===
pytest 9.0.3
=== PYPROJECT VERSION AND DEPS (venv) ===
project.version= 1.3.0
optional-dependencies= ['analytics-ui', 'dev', 'mcp', 'retrieval', 'retrieval-local', 'second-brain']
=== CHECK ANALYTICS-UI IN OPTIONAL (for dashboard) ===
analytics-ui present: True
analytics-ui deps: ['fastapi>=0.115', 'uvicorn>=0.30', 'httpx>=0.27']
...
=== FRONTEND NODE/NPM ===
v22.14.0
10.9.2
=== PACKAGE.JSON ===
{ "name": "frontend", ... (exact from run) ... }
=== LOCKFILE CHECK ===
package-lock.json present
=== NPM INSTALL (this may take time) ===
up to date, audited 263 packages in 660ms
62 packages are looking for funding
found 0 vulnerabilities
```

(Note: bare `python -m` invocations in the documented preflight script produced "command not found" in this shell environment; corrected to `.venv/bin/python -m` per repo working style in CLAUDE.md. Results are authoritative.)

## Required Preflight Decisions

- **Is the working tree clean before implementation?**  
  No. Working tree is dirty.  
  Modified (prior-phase evidence only):  
  - docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/coverage-parity-closeout.json  
  - .../coverage-parity-closeout.md  
  - .../no-raw-vector-index-proof.json  
  - .../no-raw-vector-index-proof.md  
  Untracked (planning package, tooling, root lock, and an unrelated source dir):  
  - .claude/  
  - .code-graph/  
  - docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/  
  - package-lock.json (at repo root)  
  - src/hb_assistant/source_refresh/  
  Per 02 "If Preflight Fails" guidance: these are prior user/phase changes or untracked planning artifacts. They are **not** targets of Prompt 16. For this prompt we will only create/edit: `frontend/src/lib/api.ts`, the 3 project tab pages + MyItemsPage + TodayPage + SettingsPage + DailyBriefRenderer.tsx + AdminDataConfidencePage.tsx, `tests/test_fastapi_analytics_dashboard_read_models.py` (light), new files under `docs/evidence/frontend-production-readiness-implementation/`, and light updates to architecture docs. We will not clean, overwrite, or stage the unrelated dirty/untracked items. Selective `git add` only for Prompt 16 deliverables at commit time.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes — HEAD **is exactly** the audited baseline commit. No divergence.

- **Are there new frontend/backend commits after the audit?**  
  No. The top commit in `git log --oneline -n 30` is the audit baseline itself (`be470af1`). No later commits exist on main in this tree.

- **Do any P0/P1 gaps appear already fixed?**  
  No.  
  - FPR-001 (P0): Project tab pages (`ProjectMeetingsPage.tsx`, `ProjectFieldOperationsPage.tsx`, `ProjectCostTimePage.tsx`) still use `const items = (X?.items || X || [])` followed by `.length` / `.slice(...)` — will crash on object envelopes returned by backend `build_project_*`.  
  - FPR-002 (P1): `MyItemsPage.tsx` still calls the 5 unimplemented subroute helpers (`getMyItemsActionItems`, `getMyItemsMeetings`, `getMyItemsCorrespondence`, `getMyItemsFiles`, `getMyItemsFollowedProjects`) in addition to the aggregate.  
  - FPR-006 (P1): Hash-style links (`href="#/settings"`, `href="#/today"`) still present in `TodayPage.tsx`, `SettingsPage.tsx`, and `DailyBriefRenderer.tsx`.  
  - Additionally, `frontend/src/lib/api.ts` (the thin typed client referenced throughout pages, AppShell, prior architecture/evidence, and 176/177/179) does **not exist** on disk — pages import from it; typecheck/build would currently fail or use unresolved module. Backend contracts (api.py/service.py) and tests confirm object envelopes + only `/api/my-items` (no section subs) + admin role guards + chat disabled. Gaps remain open against current repo truth.

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. `npm install` (run from frontend/) completed cleanly: "up to date, audited 263 packages in 660ms", "found 0 vulnerabilities". No `--legacy-peer-deps` flag was supplied or required.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes.  
  - `optional-dependencies=` lists 'analytics-ui' (among dev/mcp/etc.).  
  - analytics-ui deps: ['fastapi>=0.115', 'uvicorn>=0.30', 'httpx>=0.27'].  
  - `pip show fastapi` (venv): fastapi 0.136.3 installed in .venv.  
  - pyproject project.version=1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. `package-lock.json` present in frontend/ at time of check. `npm install` reported "up to date" with no modifications to the lockfile during the run.

## Additional Notes

- Repository truth is authoritative (per package 01/02/00 rules). Implementation proceeds against the exact audit HEAD with the observed dirty tree.
- No changes will be made to unrelated dirty/untracked files. Prompt 16 scope is strictly limited to the gaps listed (FPR-001, FPR-002, FPR-006 + Admin 403 baseline UI), test assertion updates for the object-envelope contract, new evidence, and required architecture cross-refs.
- Guardrails (read-only, local-first, no writeback, no raw, no chat, role guards fail-closed, CM-first labels) remain in force and will be re-confirmed in the per-prompt closeout.

## Next

Proceed to create `frontend/src/lib/api.ts` (the missing contract adapter), apply the 3 page fixes for project tabs, refactor MyItems to aggregate-only, replace hash links, add Admin 403 UI state, light test updates, run the exact validation matrix, perform browser smoke, produce the prompt-16 closeout evidence, update architecture, then selective commit. Only the final traditional commit summary+description will be emitted after the commit.

## Prompt 17 Preflight Run (re-run in sequence after Prompt 16)

Date: 2026-06-07  
Branch: main  
HEAD: 73cc61af45d2ede70bde824c2bce6fb88b1a5cc8

## Baseline Commands Executed (re-run for Prompt 17)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python):

```
=== PROMPT 17 PREFLIGHT START ===
=== GIT STATUS SHORT ===
 M docs/evidence/construction-intelligence-phase-07a-data-quality/07-obsidian-output-preview.md
 M docs/evidence/construction-intelligence-phase-07a-data-quality/obsidian-data-quality-dry-run.json
 M docs/evidence/construction-intelligence-phase-08b-automation-hardening/safe-replay-execution-proof.json
 M pyproject.toml
 M src/hb_assistant/cli/construction.py
?? .claude/
?? .code-graph/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? package-lock.json
?? src/hb_assistant/source_refresh/
?? tests/test_sources_refresh.py
=== BRANCH ===
main
=== HEAD ===
73cc61af45d2ede70bde824c2bce6fb88b1a5cc8
=== GIT LOG ONELINE -n 30 ===
73cc61af HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 16: Route/API contract hardening and launch blockers (FPR-001/002/006)
be470af1 chore(scripts): add local MCP stdio launcher for second-brain integration
... (prior)
=== PIP SHOW FASTAPI (venv) ===
Name: fastapi
Version: 0.136.3
...
=== PYTEST VERSION (venv) ===
pytest 9.0.3
=== PYPROJECT VERSION AND DEPS (venv) ===
project.version= 1.3.0
optional-dependencies= ['analytics-ui', 'dev', 'mcp', 'retrieval', 'retrieval-local', 'second-brain']
=== CHECK ANALYTICS-UI IN OPTIONAL (for dashboard) ===
analytics-ui present: True
analytics-ui deps: ['fastapi>=0.115', 'uvicorn>=0.30', 'httpx>=0.27']
=== CONFIRM PROMPT 16 EVIDENCE EXISTS (via ls, no full re-read) ===
00_PREFLIGHT.md
prompt-16-route-api-contract-hardening-closeout.md
=== FRONTEND NODE/NPM ===
v22.14.0
10.9.2
=== PACKAGE.JSON (head) ===
{ "name": "frontend", ... }
=== LOCKFILE CHECK ===
package-lock.json present
=== NPM INSTALL ===
up to date, audited 263 packages in 626ms
62 packages are looking for funding
found 0 vulnerabilities
=== PROMPT 17 PREFLIGHT COMPLETE ===
```

(Note: bare python -m corrected to .venv/bin/python per CLAUDE.md. Results authoritative.)

## Required Preflight Decisions (re-answered for Prompt 17)

- **Is the working tree clean before implementation?**  
  No. Working tree dirty. Additional modified vs. Prompt 16 preflight: pyproject.toml, src/hb_assistant/cli/construction.py, more phase-07a/08b evidence M files. Untracked now also include tests/test_sources_refresh.py (plus prior .claude/, planning pkg, root package-lock, source_refresh/, .code-graph/). The 16-delivered A files under frontend-production-readiness-implementation/ (00_PREFLIGHT, prompt-16 closeout) are prior prompt artifacts. Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 17 we will *only* create/edit: `tests/test_fastapi_analytics_today.py` (new), `frontend/src/pages/TodayPage.tsx`, `src/hb_assistant/construction/analytics/service.py` (possible light sections list), append to this 00_PREFLIGHT.md, new prompt-17 closeout md, light updates to architecture 177/176/169. Selective git add only for these at commit time.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (73cc61af...) is the Prompt 16 commit, which landed after the original audit baseline. Local main is ahead.

- **Are there new frontend/backend commits after the audit?**  
  Yes. The immediate prior commit (73cc61af) is the Prompt 16 landing ("Route/API contract hardening..."). Prompt 16 closed FPR-001/002/006 + Admin 403 baseline (with evidence). The FPR-008 gap targeted by Prompt 17 is not yet fixed in current repo truth (see below).

- **Do any P0/P1 gaps appear already fixed?**  
  No (for the Prompt 17 gap FPR-008).  
  - FPR-008 (P1): Today dashboard still renders a single "Portfolio Signals" section (sourced from the `getTodayPortfolioSignals` / `portfolioSignals` query + `portfolioItems` extraction with slice). No split into "Cost / Change / Time Signals" + "Documents and Correspondence Worth Reviewing". No explicit "Header/day context" line. No dedicated `tests/test_fastapi_analytics_today.py` exists (confirmed absent via ls/Glob in preflight). Daily Brief missing-config states already use real `<Link to="/settings">` (from Prompt 16 fix; no rework needed, will document). Backend `build_today()` still lists "portfolio_signals" in sections (single). No header context or refined split sections in the page. Gaps remain open against current repo truth.

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. Same as Prompt 16: "up to date, audited 263 packages in 626ms", "found 0 vulnerabilities". No flag needed.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. analytics-ui present with fastapi/uvicorn/httpx; fastapi 0.136.3 in venv; pyproject version 1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present; `npm install` reported "up to date" with no lock modifications during run.

## Additional Notes for Prompt 17

- Repository truth authoritative (per package rules). Implementation against current HEAD (73cc61af, post-Prompt 16).
- Prompt 16 closeout + commit confirmed to exist (ls showed the two files under the evidence dir; current HEAD is exactly the 16 commit message). Dependency satisfied: "Prompt 16 should be closed or explicitly waived with evidence."
- Prompt 17 scope strictly limited to FPR-008 (Today sections + split + header context + states + dedicated test + compact confidence). No top-level nav, no raw exposure, no new integrations, no project dashboards, no settings persistence.
- Guardrails (read-only, local-first, no writeback, no raw, advisory cost/time language, compact/secondary data confidence, chat disabled, role guards fail-closed, CM-first labels) remain in force and will be re-confirmed in the per-prompt closeout.
- Dirty/untracked files (phase evidence, pyproject, cli, untracked tests/ planning / .claude etc.) will not be cleaned, overwritten, or staged. Only Prompt 17 deliverables will be added at commit.

## Next (Prompt 17)

Create dedicated `tests/test_fastapi_analytics_today.py`, align backend today sections list lightly for contract truth, edit TodayPage to add header context + split the portfolio area into the two required sections with CM-facing states/empties/advisory copy, ensure no raw and real Link navigation for Daily Brief (already good), run full validation matrix (incl. new test), perform browser smoke, produce prompt-17 closeout, update architecture, selective commit. Only the final traditional commit summary+description will be emitted after the commit.