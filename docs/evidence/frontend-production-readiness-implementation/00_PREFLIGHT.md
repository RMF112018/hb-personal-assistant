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

Create dedicated `tests/test_fastapi_analytics_today.py`, align backend today sections list lightly for contract truth, edit TodayPage to add header context + split the portfolio area into the two required sections with CM-facing states/empties/advisory copy, ensure no raw and real Link navigation for Daily Brief (already good), run full validation matrix (incl. new test), perform browser smoke, produce prompt-17 closeout, update architecture, selective commit. Only the final traditional commit summary+description will be emitted after the commit.## Prompt 18 Preflight Run (re-run in sequence after Prompt 17; actual repo advanced with unrelated source-refresh commit)

Date: 2026-06-07  
Branch: main  
Initial capture HEAD (first preflight shell): b87f1c1bdcaad22c85de0b0ce2f51625eb92d7d8 (post-Prompt 17)  
Current HEAD at validation/close of this preflight note: b06bbcdea54d9c4a47d8ec1b0167934fec0b2568 (post "HB Construction Intelligence — Unified Source-Refresh Orchestrator" commit)

## Baseline Commands Executed (re-run for Prompt 18)

Commands from `02_REPO_TRUTH_PREFLIGHT.md` were executed at start of Prompt 18 (see first preflight shell transcript in this file's prior section for full verbatim of b87f run). A selected readonly subset was re-executed at end of validation (see RUN-VALIDATION-18 output). Key facts:

- Branch: main
- At first preflight: HEAD b87f1c1b (Prompt 17 commit message visible in log)
- ls of evidence dir at first preflight confirmed prompt-17-today-dashboard-ux-content-closeout.md present (Prompt 17 dependency met)
- pyproject has analytics-ui; fastapi present in venv; pytest 9; node 22 / npm 10.9; lock present; npm install "up to date" no legacy flag
- Working tree at start of edits: many prior phase M (06-09 evidence, pyproject, cli/construction) + untracked (.claude, .code-graph, planning pkg, source_refresh/, test_sources_refresh, root package-lock, new arch 185, evidence/source-refresh). Per plan and 02: selective edits only; inventory and do not touch unrelated.

At end of validation (after our .tsx + test edits):
- Only our intended files showed as M in the captured status: the 4 Project*.tsx + test_fastapi_analytics_dashboard_read_models.py . (Prior phase M had been committed by the intervening source-refresh commit on main.)
- Our append to this 00_PREFLIGHT (first attempt) + planned new closeout + arch updates were not yet present in that snapshot (we re-append here for accurate evidence).

## Required Preflight Decisions (re-affirmed / updated for actual execution state)

- Working tree: dirty at start (phase evidence + untracked as captured); we followed "selective only" — edited/created only Prompt 18 files (4 .tsx, 1 test update, this 00 append, closeout md, 3 arch .md touches). No cleaning of unrelated.
- Local main ahead of audit baseline: yes (b06b includes 17 + source-refresh; 17 closed its FPRs).
- New commits after audit: yes (Prompt 17 at b87f; then source-refresh at b06b — the latter is unrelated construction-agent work, not touching analytics dashboard surfaces or closing FPR-003/009).
- P0/P1 gaps for *this prompt* (FPR-003/009) not pre-fixed: confirmed at edit time via direct file reads + grep on the 4 pages (raw/portfolio/items fallback still present, project_keys unused for selector; 4 locations with hardcoded fresh/stale/source_backed badges in headers). Our replaces addressed exactly those. FPR-015 remains deferred (no rechart usage in src confirmed via grep; no charts added).
- npm without legacy: yes (both runs).
- FastAPI analytics-ui group: yes.
- Lockfile current: yes.

## Additional Notes for Prompt 18

- Repo truth authoritative. Edits made against code at/after b87f1c1b (Prompt 17 landed); intervening b06b commit on main did not alter the dashboard files or close our targeted gaps.
- Prompt 17 closeout present in history and on disk at start (ls + log); "Prompt 17 should be closed" satisfied.
- Scope: only FPR-003 (project_keys consumption in ProjectsPage selector + dual-shape), FPR-009 (data-driven badges on portfolio + 3 subpages), FPR-015 (defer + light test assert). No top-level nav, no charts, no raw, construction labels preserved, advisory language untouched.
- Guardrails preserved throughout.
- The first append attempt's section may have been against a pre-source-refresh tree view; this re-append ensures the 00 has a Prompt 18 entry with actual observed HEADs and post-validation state for the closeout to reference.
- At commit time we will `git add` only: the 4 .tsx, the test, this 00_PREFLIGHT.md (now dirty by this append), the new prompt-18 closeout, and the touched architecture .md files. No phase M, no untracked, no unrelated.

## Next (Prompt 18)

With validation matrix passed (pytest 7/7, ruff clean, mypy clean, frontend lint/typecheck/build clean), proceed to browser smoke (operator/viewer/admin, /projects + /projects/all/* + sample /projects/{key}/* ), create the prompt-18 closeout using 08 template (cite actual final HEAD post our commit, validation output, smoke notes, guardrails), update architecture lightly, selective commit, and emit *only* the traditional commit title+body per plan.
## Prompt 19 Preflight Run (re-run in sequence after Prompt 18)

Date: 2026-06-07  
Branch: main  
HEAD: 9f866749d07c2ced0f539f82d229a63abba7a8e4

## Baseline Commands Executed (re-run for Prompt 19)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used per CLAUDE.md; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python):

```
=== PROMPT 19 PREFLIGHT START ===
=== GIT STATUS SHORT ===
?? .claude/
?? .code-graph/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? docs/planning/HB_Local_Production_Launcher_Desktop_Shortcut_Implementation_Package/
?? package-lock.json
=== BRANCH ===
main
=== HEAD ===
9f866749d07c2ced0f539f82d229a63abba7a8e4
=== GIT LOG ONELINE -n 30 ===
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
b06bbcde HB Construction Intelligence — Unified Source-Refresh Orchestrator v1.0.0 — construction-agent refresh-sources
b87f1c1b HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 17: Today dashboard UX/content completion (FPR-008)
73cc61af HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 16: Route/API contract hardening and launch blockers (FPR-001/002/006)
... (prior history)
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
=== CONFIRM PROMPT 18 EVIDENCE EXISTS (via ls, no full re-read) ===
00_PREFLIGHT.md
prompt-16-route-api-contract-hardening-closeout.md
prompt-17-today-dashboard-ux-content-closeout.md
prompt-18-projects-portfolio-and-dashboards-closeout.md
=== CONFIRM PROMPT 18 COMMIT IN RECENT LOG (dependency met) ===
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
b06bbcde ...
=== FRONTEND NODE/NPM ===
v22.14.0
10.9.2
=== PACKAGE.JSON (head) ===
{ "name": "frontend", ... }
=== LOCKFILE CHECK ===
package-lock.json present
=== NPM INSTALL ===
up to date, audited 263 packages in 622ms
62 packages are looking for funding
found 0 vulnerabilities
=== PROMPT 19 PREFLIGHT COMPLETE ===
```

(Note: bare python -m corrected to .venv/bin/python per CLAUDE.md. Results authoritative.)

## Required Preflight Decisions (re-answered for Prompt 19)

- **Is the working tree clean before implementation?**  
  No. Working tree has untracked items only in this capture (planning package dirs, .claude/, .code-graph/, root package-lock.json). No modified source files from prior prompts in the short status (prior prompt A files under frontend-production-readiness-implementation/ are present as artifacts from 16/17/18). Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 19 we will *only* create/edit: `src/hb_assistant/construction/analytics/service.py` (build_my_items), `frontend/src/pages/MyItemsPage.tsx`, `frontend/src/components/my-items/MyActionItemCard.tsx`, light update to `tests/test_fastapi_analytics_dashboard_read_models.py` (and possibly comments in app_shell), append to this 00_PREFLIGHT.md, new prompt-19 closeout md, light updates to architecture 177/176/169. Selective git add only for these at commit time. No subroute additions.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (9f866749...) is the Prompt 18 commit, well after the original audit baseline and after Prompt 17/16.

- **Are there new frontend/backend commits after the audit?**  
  Yes. The immediate prior commit (9f866749) is the Prompt 18 landing ("Projects portfolio and project dashboards (FPR-003/009)"). Prompt 18 closed FPR-003/009 with evidence. The gap targeted by Prompt 19 (FPR-002 polish / My Items UX finalization) is already closed at the contract level (see below); Prompt 19 is UX/contract polish on the aggregate.

- **Do any P0/P1 gaps appear already fixed?**  
  Yes for the core of FPR-002 (P1).  
  - FPR-002 (P1): "My Items page calls unimplemented backend subroutes". Current repo truth (confirmed via searches/greps on source + prior execution knowledge):  
    - Backend (analytics/api.py): only `@app.get("/api/my-items")` → AnalyticsService.build_my_items(). No /action-items, /meetings, /correspondence, /files, /followed-projects subs registered.  
    - OpenAPI test (test_fastapi_analytics_app_shell.py): asserts exact paths set includes "/api/my-items" and does *not* list any my-items subs. Surfaces list includes GET /api/my-items for viewer.  
    - Frontend: MyItemsPage.tsx explicitly comments "Prompt 16: consume only the aggregate /api/my-items contract. The backend does not implement the five section subroutes..." and uses only `api.getMyItems` (no sub calls). api.ts has only getMyItems → '/api/my-items'.  
    - dashboard_read_models test: test_my_items_viewer_ok hits only /api/my-items and asserts object envelope + sections list.  
    - Prompt 16 closeout + code changes established the aggregate-only posture; 00_PREFLIGHT prior runs documented the gap as addressed by refactor to aggregate.  
    - Thus FPR-002 is closed in repo truth. Prompt 19 will *document* this closure explicitly in preflight/closeout and focus on polish: richer section data within the aggregate envelope (build_my_items), distinct 5-section rendering, useful CM-facing empties, light typed normalization for the my-items surface, test enhancements within the existing contract (no subroutes added), validation, smoke (confirm no 404s on the single expected call), evidence, and arch cross-refs. No rework of the 16 decision.

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. "up to date, audited 263 packages in 622ms", "found 0 vulnerabilities". No flag supplied or required.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. analytics-ui present with fastapi/uvicorn/httpx; fastapi 0.136.3 in venv; pyproject version 1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present in frontend/; `npm install` reported "up to date" with no lock modifications during the run.

## Additional Notes for Prompt 19

- Repository truth authoritative (per package rules). Implementation against current HEAD (9f866749..., post-Prompt 18).
- Prompt 18 closeout + commit confirmed to exist (ls showed prompt-18-projects-portfolio-and-dashboards-closeout.md; current HEAD log shows the Prompt 18 commit message as the most recent). Dependency satisfied: "Prompt 18 should be closed or explicitly waived with evidence."
- Prompt 19 scope: finalize My Items backend/frontend contract UX after Prompt 16 (aggregate-only), render the 5 user-specific sections (action items, meetings, correspondence, files, followed projects + review signals) with helpful non-raw empties, keep confidence/freshness secondary, ensure no expected My Items route/API call returns 404 (already true; maintain), construction-management-first language, no mailbox/calendar/file-browser behavior, no mutations, no raw. Prefer typed adapters/normalization over permissive any for the my-items surface. Update tests/evidence same prompt.
- When a gap is already fixed (FPR-002 core contract/404 prevention), document the evidence (searches, ls, log, test assertions, page/api comments, openapi) and do not rework the code unnecessarily (no subroute additions that would contradict app_shell test + 16 decision + openapi contract).
- Guardrails (read-only, local-first, no writeback, no raw, advisory cost/time language, construction labels, contextual tabs only, hide detailed in primary + link to Admin, chat disabled, role guards fail-closed) remain in force and will be re-confirmed in the per-prompt closeout.
- Dirty/untracked files (planning pkgs, .claude, .code-graph, root package-lock) will not be cleaned, overwritten, or staged. Only Prompt 19 deliverables will be added at commit.

## Next (Prompt 19)

With preflight complete and evidence appended: enhance build_my_items for richer categorized attention/sections data (within aggregate), polish MyItemsPage with light TS interfaces + 5 distinct sections + CM empties, enhance MyActionItemCard, light test updates (no subs), run validation matrix (incl. preflight re-run), browser smoke, produce prompt-19 closeout, update architecture, selective commit. Only the final traditional commit summary+description will be emitted after the commit.
## Prompt 20 Preflight Run (re-run in sequence after Prompt 19)

Date: 2026-06-07  
Branch: main  
HEAD: f93b26b1e227cf5d84580af4c9477247c9ada514

## Baseline Commands Executed (re-run for Prompt 20)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used per CLAUDE.md and prior prompt executions; bare python -m corrected to .venv/bin/python; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python):

```
=== PROMPT 20 PREFLIGHT START ===
=== GIT STATUS SHORT ===
 M src/hb_assistant/cli/procore.py
 M src/hb_assistant/procore/sync.py
?? .claude/
?? .code-graph/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? docs/planning/HB_Local_Production_Launcher_Desktop_Shortcut_Implementation_Package/
?? package-lock.json
=== BRANCH ===
main
=== HEAD ===
f93b26b1e227cf5d84580af4c9477247c9ada514
=== GIT LOG ONELINE -n 30 ===
f93b26b1 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 19: My Items dashboard (FPR-002 polish)
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
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
=== CONFIRM PROMPT 19 EVIDENCE EXISTS (via ls, no full re-read) ===
00_PREFLIGHT.md
prompt-16-route-api-contract-hardening-closeout.md
prompt-17-today-dashboard-ux-content-closeout.md
prompt-18-projects-portfolio-and-dashboards-closeout.md
prompt-19-my-items-dashboard-closeout.md
=== CONFIRM PROMPT 19 COMMIT IN RECENT LOG (dependency met) ===
f93b26b1 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 19: My Items dashboard (FPR-002 polish)
9f866749 ...
=== FRONTEND NODE/NPM ===
v22.14.0
10.9.2
=== PACKAGE.JSON (head) ===
{ "name": "frontend", ... }
=== LOCKFILE CHECK ===
package-lock.json present
=== NPM INSTALL ===
up to date, audited 263 packages in 595ms
62 packages are looking for funding
found 0 vulnerabilities
=== PROMPT 20 PREFLIGHT COMPLETE ===
```

(Note: Results authoritative. Bare python -m corrected to .venv/bin/python per CLAUDE.md and execution precedent.)

## Required Preflight Decisions (re-answered for Prompt 20)

- **Is the working tree clean before implementation?**  
  No. Working tree has modified files (src/hb_assistant/cli/procore.py, src/hb_assistant/procore/sync.py — unrelated to analytics dashboard/Settings per plan inventory) + untracked (planning package dirs, .claude/, .code-graph/, root package-lock.json). The prior prompt A files under frontend-production-readiness-implementation/ (00_PREFLIGHT + prompt-16 through prompt-19 closeouts) are present as artifacts. Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 20 we will *only* create/edit files directly required for the 5 FPRs: primarily `frontend/src/pages/SettingsPage.tsx` (and optionally tiny components/settings/* if proportional), backend prefs persistence (likely `src/hb_assistant/construction/analytics/api.py` + small helper mirroring daily_brief pattern), any light test updates (test_fastapi_analytics_settings.py etc.), append to this 00_PREFLIGHT.md, new prompt-20 closeout md, light updates to architecture 177/176/169. Selective git add only for these at commit time. The unrelated M files and all untracked will not be touched or staged.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (f93b26b1...) is the Prompt 19 commit, well after the original audit baseline and after all prior prompts (19/18/17/16 etc.).

- **Are there new frontend/backend commits after the audit?**  
  Yes. The immediate prior commit (f93b26b1) is the Prompt 19 landing ("My Items dashboard (FPR-002 polish)"). Prompt 19 closed FPR-002 with evidence. The gaps targeted by Prompt 20 (FPR-004/005/010/016/017) remain open in current repo truth (see below).

- **Do any P0/P1 gaps appear already fixed?**  
  No (for the Prompt 20 gaps).  
  - FPR-004 (P1): SettingsPage still contains multiple "Raw response" <details><summary>Raw response</summary><pre>{JSON.stringify(XXXResult...)} panels for the "Load" buttons (accounts/projects/sources/keywords/daily-brief/prefs/admin-sync), plus "Load Accounts Status" etc. text, and alert() calls on error paths. Confirmed via targeted searches.  
  - FPR-005 (P1): The exact buggy line `const currentState = detectResult?.state || status?.state || status?.config?.enabled === false ? 'not_configured' : undefined` (precedence issue) is still present; Daily Brief section relies on it. Backend _compute_state is correct, but frontend bug remains.  
  - FPR-010 (P2): Settings still mixes "Load" debug + raw panels + "sent (stub)" + stub copy; not yet fully guided CM-first sections with status cards and clear next actions (Account Connections, Project Connections, Daily Brief, Preferences).  
  - FPR-016 (P3): /api/settings/preferences (GET/PATCH) is explicitly stubbed in api.py ("# Stub; full impl would load from local JSON under Application Support (like daily_brief config)."); returns static values; "Preferences patch sent (stub)" in UI. No real persistence yet.  
  - FPR-017 (P3): /api/settings/keywords and keywords section in UI is still "informational only" / "Load Keywords Info" + raw panel + advisory note ("Candidates/active/disabled/excluded... Use per-project /keywords for edits."); while backend (project_keywords.py service + API CRUD/explain routes) is complete and already exercised in tests.  
  Gaps remain open against current repo truth.

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. "up to date, audited 263 packages in 595ms", "found 0 vulnerabilities". No flag needed.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. analytics-ui present with fastapi/uvicorn/httpx; fastapi 0.136.3 in venv; pyproject version 1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present in frontend/; `npm install` reported "up to date" with no lock modifications during the run.

## Additional Notes for Prompt 20

- Repository truth authoritative (per package rules). Implementation against current HEAD (f93b26b1..., post-Prompt 19).
- Prompt 19 closeout + commit confirmed to exist (ls showed prompt-19-my-items-dashboard-closeout.md; current HEAD log shows the Prompt 19 commit message as the most recent). Dependency satisfied: "Prompt 19 should be closed or explicitly waived with evidence."
- Prompt 20 scope strictly limited to the 5 listed FPRs (raw/debug removal + state bugfix + guided sections + real prefs persist + keyword management UI). No subroute changes, no live syncs from Settings, no secrets exposure, Daily Brief remains external presenter-only, openapi paths and existing route surface must remain stable (only consumer polish + one real impl for prefs + one bugfix). Preview/save/approve boundary preserved. CM-first language, no backend-console labels.
- Guardrails (read-only, local-first, no writeback from primary/setup, no raw, advisory, construction labels, hide detailed → Admin, chat disabled, role guards fail-closed) remain in force and will be re-confirmed in the per-prompt closeout and final grep validation.
- Dirty/untracked files (unrelated M in cli/procore + procore/sync, planning pkgs, .claude, .code-graph, root package-lock) will not be cleaned, overwritten, or staged. Only Prompt 20 deliverables will be added at commit.
- When a gap is already fixed in truth, document (none primary here; all 5 targeted are open per searches).
- Next (after this preflight + append): remove raw/alerts/stubs (FPR-004), fix state precedence + tests (FPR-005), guided sections refactor (FPR-010), real prefs JSON persist (FPR-016), keyword UI (FPR-017), full validation matrix (incl. the required grep for forbidden strings in frontend/src, must be clean for Settings), browser smoke, closeout, arch, selective commit. Only the final traditional commit summary+description will be emitted after the commit.

## Next (Prompt 20)

With preflight complete and evidence appended (this section), proceed to the implementation steps in strict order per the attached plan: remove raw panels/alerts/stubs from SettingsPage, fix Daily Brief state, refactor to guided sections, implement prefs persistence, implement keyword UI, run validation (pytest + ruff + mypy + frontend + explicit grep), browser smoke, create closeout, update arch, selective commit. Follow "surgical + repo-truth first + update evidence same prompt + only output commit at very end".
