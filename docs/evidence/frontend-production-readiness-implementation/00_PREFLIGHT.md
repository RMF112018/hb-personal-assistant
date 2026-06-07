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

## Prompt 22 Preflight Run (re-run in sequence after Prompt 21)

Date: 2026-06-07  
Branch: main  
HEAD: e078b8d7c092236e56d3ef950e804e9161d76073

## Baseline Commands Executed (re-run for Prompt 22)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used per CLAUDE.md and prior prompt executions; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python):

```
=== PROMPT 22 PREFLIGHT START ===
Sun Jun  7 04:52:59 EDT 2026
=== git status --short ===
 M frontend/src/pages/SettingsPage.tsx
 M src/hb_assistant/construction/analytics/api.py
?? .claude/
?? .code-graph/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? docs/planning/HB_Local_Production_Launcher_Desktop_Shortcut_Implementation_Package/
?? package-lock.json
=== git branch --show-current ===
main
=== git rev-parse HEAD ===
e078b8d7c092236e56d3ef950e804e9161d76073
=== git log --oneline -n 30 ===
e078b8d7 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 21: Admin / Data Confidence polish (FPR-007)
a0989799 HB Construction Intelligence — Procore Multi-Project Sync Fix v1.0.1 — all-project sync no longer crashes on "multi"
13a75675 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 20: Settings and onboarding polish (FPR-004/005/010/016/017)
f93b26b1 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 19: My Items dashboard (FPR-002 polish)
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
b06bbcde HB Construction Intelligence — Unified Source-Refresh Orchestrator v1.0.0 — construction-agent refresh-sources
b87f1c1b HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 17: Today dashboard UX/content completion (FPR-008)
73cc61af HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 16: Route/API contract hardening and launch blockers (FPR-001/002/006)
be470af1 chore(scripts): add local MCP stdio launcher for second-brain integration
9708be56 chore(evidence): refresh phase 06–09 evidence bundles after validation baseline
... (prior)
=== .venv/bin/python -m pip show fastapi || true ===
Name: fastapi
Version: 0.136.3
...
=== .venv/bin/python -m pytest --version ===
pytest 9.0.3
=== pyproject probe (.venv python) ===
project.version= 1.3.0
optional-dependencies= ['analytics-ui', 'dev', 'mcp', 'retrieval', 'retrieval-local', 'second-brain']
=== cd frontend; node --version ===
v22.14.0
=== npm --version ===
10.9.2
=== cat frontend/package.json (head) ===
{ "name": "frontend", ... }
=== package-lock check ===
package-lock.json present (size: 143765 )
=== npm install (frontend) ===
up to date, audited 263 packages in 642ms
... found 0 vulnerabilities
=== evidence closeouts ls (to confirm P21 dep) ===
00_PREFLIGHT.md
prompt-16-route-api-contract-hardening-closeout.md
prompt-17-today-dashboard-ux-content-closeout.md
prompt-18-projects-portfolio-and-dashboards-closeout.md
prompt-19-my-items-dashboard-closeout.md
prompt-20-settings-onboarding-polish-closeout.md
prompt-21-admin-data-confidence-polish-closeout.md
=== PROMPT 22 PREFLIGHT END ===
Sun Jun  7 04:53:00 EDT 2026
```

(Note: bare python -m corrected to .venv/bin/python per CLAUDE.md. Results authoritative.)

## Required Preflight Decisions (re-answered for Prompt 22)

- **Is the working tree clean before implementation?**  
  No. Working tree dirty with M frontend/src/pages/SettingsPage.tsx (incidental from prior session work), M src/hb_assistant/construction/analytics/api.py (unrelated Procore-adjacent), + untracked (.claude/, .code-graph/, docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/, HB_Local_Production_Launcher..., root package-lock.json). Prior A files (prompt-21 closeout etc.) are artifacts. Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 22 we will *only* create/edit: new/changed under `frontend/src/components/ui/` (ErrorState etc.), `frontend/src/layouts/AppShell.tsx`, `frontend/src/index.css`, `frontend/src/pages/SettingsPage.tsx` (error/label polish), append to this 00_PREFLIGHT.md, new prompt-22 closeout md, light updates to architecture 176 (primary). Selective git add only for these at commit time.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (e078b8d7...) is the Prompt 21 commit (far after the original audit baseline and after 20/19/18/17/16).

- **Are there new frontend/backend commits after the audit?**  
  Yes. The top commit (e078b8d7) is the Prompt 21 landing ("Admin / Data Confidence polish (FPR-007)"). Prompt 21 closed FPR-007 with evidence. The gaps targeted by Prompt 22 (FPR-011/013) are the current focus; FPR-011 appears already clean in repo truth.

- **Do any P0/P1 gaps appear already fixed?**  
  For this prompt's gaps:  
  - FPR-011 (P2): "alert() error handling remains in Settings". Current repo truth (targeted grep run during this preflight): `grep -R "alert(" -n frontend/src || true` returned "No matches (already clean per research)". No alert() calls in frontend/src. The gap is already fixed in repo truth (likely cleaned in Prompt 20 Settings polish). Per plan guidance "When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily." Prompt 22 will confirm via the required `grep -R "alert(" ...` in validation, document in closeout, and only introduce the shared ErrorState for future consistency / to address any remaining inline red divs as part of FPR-013 polish. No code change needed purely for alert() removal.
  - FPR-013 (P2): "Responsive/accessibility baseline is incomplete". Current patterns observed via Glob/Grep/prior context (no full re-read of restricted files): sidebar is fixed `w-56` always visible in AppShell (no collapse); focus-visible only on `a, button` in index.css (no coverage for input/select/textarea or role selector); no skip link; `<main>` exists but no `id="main"`; navs have `aria-label`; ad-hoc loading states (`<div className="p-6 text-sm text-[var(--hb-muted)]">Loading ...</div>`) repeated in Today/Projects/MyItems/3 project tabs/ProjectDashboard/Admin; Settings uses 8+ per-section `{xxxError && <div className="text-xs text-red-500">{msg}</div>}` (no shared component); some form controls have labels but keyword inputs and certain selects/checkboxes could be more explicit. These are incomplete but not absent. Prompt 22 will implement the recommended fixes (ErrorState, focus extension, skip+id, sidebar lightweight collapse, label audit + ErrorState swap in Settings, optional LoadingState normalization) while documenting the baseline state.

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. "up to date, audited 263 packages in 642ms", "found 0 vulnerabilities". No flag supplied or required.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. 'analytics-ui' in optional-dependencies list; fastapi 0.136.3 present in venv.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present (size ~143k); `npm install` reported "up to date" with no lock modifications.

## Additional Notes for Prompt 22

- Repository truth authoritative (per package rules). Implementation against current HEAD (e078b8d7..., post-Prompt 21).
- Prompt 21 closeout + commit confirmed to exist (ls during preflight listed `prompt-21-admin-data-confidence-polish-closeout.md`; current HEAD log top is exactly the Prompt 21 commit message; head of the closeout file confirmed content). Dependency satisfied: "Prompt 21 should be closed or explicitly waived with evidence."
- Prompt 22 scope strictly limited to FPR-011 (confirm/document alert-free + introduce shared ErrorState for inline errors) and FPR-013 (focus styles, skip link + semantic main, sidebar responsive collapse (lightweight), consistent ErrorState/Loading patterns, Settings form label audit + error consolidation). No new heavy deps (Tailwind + existing lucide; clsx/tailwind-merge already in package if needed for class merging but not required). No charts, no major redesign, no changes to API contracts/role guards, no raw exposure, CM-first language preserved.
- When a gap is already fixed (FPR-011 alert() — 0 matches), document the evidence (grep output in preflight + validation) and do not rework unnecessarily. The ErrorState addition is additive for coherence (FPR-013) and future-proofing.
- Guardrails (read-only, local-first, no writeback, no raw, advisory only, construction-management-first labels, contextual subnav only, hide detailed → Admin, chat disabled, role guards fail-closed, local role dev simulation only) remain in force and will be re-confirmed in the per-prompt closeout.
- Dirty/untracked files (Settings M incidental, unrelated api.py M, planning pkgs, .claude, .code-graph, root package-lock) will not be cleaned, overwritten, or staged. Only Prompt 22 deliverables will be added at commit.
- Preflight captured exact baseline for the closeout evidence.

## Next (Prompt 22)

With preflight complete and evidence appended (this section), proceed to the implementation steps in strict order per the attached plan: add ErrorState (and optional LoadingState) under ui/, confirm no alert() (document), extend focus-visible, add skip link + #main, improve AppShell sidebar for narrow widths (light collapse + toggle + a11y), update Settings to use ErrorState + explicit labels, normalize loading if component added, run full validation matrix (lint/type/build + required grep alert + preflight re-run), browser smoke (keyboard + responsive per spec), create prompt-22 closeout, light arch update (176 primary), selective commit with traditional title, emit *only* the commit summary+description at end. Follow surgical + repo-truth first + update evidence same prompt + only output commit at very end. Mark preflight-22 completed and advance todos.

## Prompt 23 Preflight Run (re-run in sequence after Prompt 22)

Date: 2026-06-07  
Branch: main  
HEAD: 69661507312711eb573aeb958d4dde2aaf415c90

## Baseline Commands Executed (re-run for Prompt 23)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used per CLAUDE.md and prior prompt executions; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python; plus targeted gap confirmation greps/ls for FPR-012/018 and P22 dep):

```
=== PROMPT 23 PREFLIGHT START ===
Sun Jun  7 05:01:55 EDT 2026
=== git status --short ===
 M src/hb_assistant/construction/analytics/api.py
?? .claude/
?? .code-graph/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? docs/planning/HB_Local_Production_Launcher_Desktop_Shortcut_Implementation_Package/
?? package-lock.json
=== git branch --show-current ===
main
=== git rev-parse HEAD ===
69661507312711eb573aeb958d4dde2aaf415c90
=== git log --oneline -n 30 ===
69661507 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 22: UI kit, accessibility, responsiveness consolidation (FPR-011/013)
e078b8d7 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 21: Admin / Data Confidence polish (FPR-007)
a0989799 HB Construction Intelligence — Procore Multi-Project Sync Fix v1.0.1 — all-project sync no longer crashes on "multi"
13a75675 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 20: Settings and onboarding polish (FPR-004/005/010/016/017)
f93b26b1 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 19: My Items dashboard (FPR-002 polish)
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
b06bbcde HB Construction Intelligence — Unified Source-Refresh Orchestrator v1.0.0 — construction-agent refresh-sources
b87f1c1b HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 17: Today dashboard UX/content completion (FPR-008)
73cc61af HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 16: Route/API contract hardening and launch blockers (FPR-001/002/006)
be470af1 chore(scripts): add local MCP stdio launcher for second-brain integration
9708be56 chore(evidence): refresh phase 06–09 evidence bundles after validation baseline
... (prior)
=== .venv/bin/python -m pip show fastapi || true ===
Name: fastapi
Version: 0.136.3
...
=== .venv/bin/python -m pytest --version ===
pytest 9.0.3
=== pyproject probe (.venv python) ===
project.version= 1.3.0
optional-dependencies= ['analytics-ui', 'dev', 'mcp', 'retrieval', 'retrieval-local', 'second-brain']
=== cd frontend; node --version ===
v22.14.0
=== npm --version ===
10.9.2
=== cat frontend/package.json ===
{ "name": "frontend", ... (no "test", "vitest", "playwright", or "smoke" scripts) }
=== package-lock check ===
package-lock.json present (size: 143765 )
=== npm install (frontend) ===
up to date, audited 263 packages...
found 0 vulnerabilities
=== confirm P22 closeout dep (ls evidence) ===
00_PREFLIGHT.md
prompt-16-route-api-contract-hardening-closeout.md
...
prompt-22-ui-kit-accessibility-responsiveness-closeout.md
=== quick gap confirmation for FPR-012/018 (no vitest/playwright/test/smoke in frontend) ===
No test/vitest/playwright/smoke scripts found in package.json
No vitest/playwright config files
No *.test.* or *.spec.* files under frontend/src
=== PROMPT 23 PREFLIGHT END ===
Sun Jun  7 05:01:57 EDT 2026
```

(Note: bare python -m corrected to .venv/bin/python per CLAUDE.md. Results authoritative. Gap confirmation greps/ls performed as part of preflight run.)

## Required Preflight Decisions (re-answered for Prompt 23)

- **Is the working tree clean before implementation?**  
  No. Working tree has M src/hb_assistant/construction/analytics/api.py (unrelated to frontend/testing per plan inventory) + untracked (planning package dirs, .claude/, .code-graph/, root package-lock.json). The prior A files under frontend-production-readiness-implementation/ (00_PREFLIGHT + prompt-16 through prompt-22 closeouts) are present as artifacts. Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 23 we will *only* create/edit: `frontend/package.json`, new `frontend/vitest.config.ts` + `frontend/src/test/setup.ts` + test files under `frontend/src/components/ui/` (and optionally thin api/envelope tests), new `scripts/smoke_local.py` (+ optional thin .sh), append to this 00_PREFLIGHT.md, new prompt-23 closeout md, light updates to architecture 176 (or 170). Selective git add only for these at commit time.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (69661507...) is the Prompt 22 commit, far after the original audit baseline and after Prompt 21/20/etc.

- **Are there new frontend/backend commits after the audit?**  
  Yes. The top commit (69661507) is the Prompt 22 landing ("UI kit, accessibility, responsiveness consolidation (FPR-011/013)"). Prompt 22 closed FPR-011/013 with evidence. The gaps targeted by Prompt 23 (FPR-012/018) remain open in current repo truth (see below).

- **Do any P0/P1 gaps appear already fixed?**  
  No (for the Prompt 23 gaps FPR-012/018).  
  - FPR-012 (P2): "No frontend test harness found". Current repo truth (confirmed via Glob/Grep/Read + the quick confirmation run during this preflight): `frontend/package.json` has no "test", "vitest", "playwright", or "smoke" scripts; no `vitest.config.*` or `playwright.config.*`; no `frontend/src/**/*.{test,spec}.*` or `frontend/tests/*` files. Dev deps have no vitest/@testing-library/* /jsdom. The 06_VALIDATION_MATRIX describes only manual two-terminal steps (uvicorn + npm run dev) plus "npm run lint && typecheck && build"; no `npm run test` or harness.  
  - FPR-018 (P3): "End-to-end local smoke harness and runbook are not yet packaged". No `scripts/smoke*` (only unrelated proofs in scripts/proofs/); no documented one-command/scripted local smoke that starts/verifies backend surfaces the UI calls + frontend build + vitest + fails on expected 404s or bad envelope shapes. The matrix and prior closeouts reference manual visual smoke and "run the commands"; no packaged harness script producing evidence.  
  - Prompt 22 dep met: ls during preflight listed `prompt-22-ui-kit-accessibility-responsiveness-closeout.md`; current HEAD log top is exactly the Prompt 22 commit message. Dependency satisfied: "Prompt 22 should be closed or explicitly waived with evidence."  
  Gaps remain open against current repo truth.

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. "up to date, audited 263 packages...", "found 0 vulnerabilities". No flag needed.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. 'analytics-ui' in optional-dependencies list; fastapi 0.136.3 in venv; pyproject version 1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present (size ~143k); `npm install` reported "up to date" with no lock modifications.

## Additional Notes for Prompt 23

- Repository truth authoritative (per package rules). Implementation against current HEAD (69661507..., post-Prompt 22).
- Prompt 22 closeout + commit confirmed to exist (ls listed it; log top is the P22 message). Dependency satisfied.
- Prompt 23 scope strictly limited to FPR-012 (add Vitest + RTL + jsdom harness + "test"/"smoke" scripts + small component/adapter tests focused on P22 primitives + contract protection) and FPR-018 (add `scripts/smoke_local.py` using the established tmp-DB + TestClient(create_app) pattern already used by app_shell/daily-brief/etc.; exercises the exact UI-facing surfaces from 06_VALIDATION_MATRIX + prior prompts; asserts envelope keys + no raw; drives frontend build + new vitest; prints evidence-ready summary; optional thin .sh wrapper; plus record the two-terminal visual smoke steps from the matrix with role switch and "no expected 404s" checks). No Playwright (per risk note: scripted API/route smoke + document as future). No real operator DB/auth cache/Obsidian. All fixtures temp. Update tests/evidence same prompt. When a sub-part is already covered (manual steps in 06), enhance/document rather than duplicate.
- Guardrails (read-only, local-first, no writeback, no raw, advisory, construction-management-first labels, hide detailed → Admin, chat disabled, role guards fail-closed, local role dev simulation only) remain in force and will be re-confirmed in the per-prompt closeout.
- Dirty/untracked files (unrelated M, planning pkgs, .claude, .code-graph, root package-lock) will not be cleaned, overwritten, or staged. Only Prompt 23 deliverables will be added at commit.
- Preflight captured exact baseline + gap confirmation for the closeout evidence.

## Next (Prompt 23)

With preflight complete and evidence appended (this section), proceed to the implementation steps in strict order per the attached plan: add Vitest + RTL harness + scripts to frontend/, write initial component/adapter tests (ErrorState/LoadingState + contract protection), implement the smoke_local.py harness (TestClient for UI surfaces + drive build/vitest), run full validation matrix (listed pytest + frontend lint/type/build + `npm run test -- --run` + new smoke + re-run readonly preflight), record browser smoke notes (06 matrix visual), create prompt-23 closeout, light arch update, selective commit with traditional title, emit *only* the commit summary+description at end. Follow surgical + repo-truth first + update evidence same prompt + only output commit at very end. Mark preflight-23 completed and advance todos.

## Prompt 24 Preflight Run (re-run in sequence after Prompt 23)

Date: 2026-06-07  
Branch: main  
HEAD: 2f06b841551dc96989942f01efc5b42f05c08594

## Baseline Commands Executed (re-run for Prompt 24)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used per CLAUDE.md and prior prompt executions; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python; plus targeted gap confirmation greps/ls for FPR-014 and P23 dep + FPR-016 already-closed evidence):

```
=== PROMPT 24 PREFLIGHT START ===
Sun Jun  7 05:14:30 EDT 2026
=== git status --short ===
 M config/config.example.yml
 M frontend/package-lock.json
 M src/hb_assistant/cli/construction.py
 M src/hb_assistant/config/models.py
 M src/hb_assistant/construction/analytics/api.py
 M src/hb_assistant/source_refresh/orchestrator.py
?? .claude/
?? .code-graph/
?? docs/planning/HB_Auth_Onboarding_Implementation_Package/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? docs/planning/HB_Local_Production_Launcher_Desktop_Shortcut_Implementation_Package/
?? package-lock.json
?? src/hb_assistant/launcher/
?? src/hb_assistant/scheduler/
=== git branch --show-current ===
main
=== git rev-parse HEAD ===
2f06b841551dc96989942f01efc5b42f05c08594
=== git log --oneline -n 30 ===
2f06b841 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 23: End-to-end local smoke harness (FPR-012/018)
69661507 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 22: UI kit, accessibility, responsiveness consolidation (FPR-011/013)
e078b8d7 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 21: Admin / Data Confidence polish (FPR-007)
a0989799 HB Construction Intelligence — Procore Multi-Project Sync Fix v1.0.1 — all-project sync no longer crashes on "multi"
13a75675 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 20: Settings and onboarding polish (FPR-004/005/010/016/017)
f93b26b1 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 19: My Items dashboard (FPR-002 polish)
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
b06bbcde HB Construction Intelligence — Unified Source-Refresh Orchestrator v1.0.0 — construction-agent refresh-sources
b87f1c1b HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 17: Today dashboard UX/content completion (FPR-008)
73cc61af HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 16: Route/API contract hardening and launch blockers (FPR-001/002/006)
be470af1 chore(scripts): add local MCP stdio launcher for second-brain integration
9708be56 chore(evidence): refresh phase 06–09 evidence bundles after validation baseline
... (prior)
=== .venv/bin/python -m pip show fastapi || true ===
Name: fastapi
Version: 0.136.3
...
=== .venv/bin/python -m pytest --version ===
pytest 9.0.3
=== pyproject probe (.venv python) ===
project.version= 1.3.0
optional-dependencies= ['analytics-ui', 'dev', 'mcp', 'retrieval', 'retrieval-local', 'second-brain']
=== cd frontend; node --version ===
v22.14.0
=== npm --version ===
10.9.2
=== cat frontend/package.json ===
{ "name": "frontend", ... (has "test", "vitest", "smoke:frontend" from P23) }
=== package-lock check ===
package-lock.json present (size: 261580 )
=== npm install (frontend) ===
... (normal run; "To address all issues (including breaking changes), run: npm audit fix --force" advisory note only; no --legacy-peer-deps flag supplied or used)
=== confirm P23 closeout dep (ls evidence) ===
00_PREFLIGHT.md
...
prompt-23-end-to-end-local-smoke-harness-closeout.md
=== confirm P23 commit in log ===
2f06b841 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 23: End-to-end local smoke harness (FPR-012/018)
...
=== quick gap confirmation for FPR-014 (daily brief fixtures) ===
No daily_brief_analytics fixtures dir yet (expected open per spec)
=== quick confirmation FPR-016 prefs real (grep evidence) ===
tests/test_fastapi_analytics_settings.py:133:    # Prompt 20 FPR-016: real persist (re-GET reflects, schema present after save)
src/hb_assistant/construction/analytics/api.py:622:    # Prompt 20: real local JSON preferences persistence (FPR-016), mirroring daily_brief pattern.
src/hb_assistant/construction/analytics/api.py:623:    def _prefs_config_path() -> Path:
...
src/hb_assistant/construction/analytics/api.py:627:        return base / "ui_preferences.json"
...
=== PROMPT 24 PREFLIGHT END ===
Sun Jun  7 05:14:31 EDT 2026
```

(Note: bare python -m corrected to .venv/bin/python per CLAUDE.md. Results authoritative. Gap confirmation greps/ls performed as part of preflight run. FPR-016 references confirm real impl from Prompt 20.)

## Required Preflight Decisions (re-answered for Prompt 24)

- **Is the working tree clean before implementation?**  
  No. Working tree has several M (unrelated to P24 per plan: config/config.example.yml, frontend/package-lock.json (from prior), src/hb_assistant/cli/construction.py, config/models.py, construction/analytics/api.py (incidental from before), source_refresh/orchestrator.py) + untracked (planning package dirs, .claude/, .code-graph/, root package-lock.json, new src/hb_assistant/launcher/ and scheduler/ dirs). The prior A files under frontend-production-readiness-implementation/ (00_PREFLIGHT + prompt-16 through prompt-23 closeouts) are present as artifacts. Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 24 we will *only* create/edit: `tests/fixtures/daily_brief_analytics/*.md` (new), edit `tests/test_fastapi_analytics_daily_brief.py`, new `frontend/src/components/ui/ErrorBoundary.tsx` + edit to `frontend/src/main.tsx` (or routes.tsx), (optionally) `scripts/proofs/frontend_safety_scan.py` + receipt, append to this 00_PREFLIGHT.md, new prompt-24 closeout md, light updates to architecture .md(s). Selective git add only for these at commit time.

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (2f06b841...) is the Prompt 23 commit, far after the original audit baseline and after Prompt 22/21/20/etc.

- **Are there new frontend/backend commits after the audit?**  
  Yes. The top commit (2f06b841) is the Prompt 23 landing ("End-to-end local smoke harness (FPR-012/018)"). Prompt 23 closed FPR-012/018 with evidence. The gaps targeted by Prompt 24 (FPR-014 open; FPR-016 already closed in repo truth per P20) are handled per spec below.

- **Do any P0/P1 gaps appear already fixed?**  
  N/A (P24 targets P2/P3).  
  - FPR-014 (P2): "Daily Brief latest endpoint returns bounded Markdown content; needs explicit no-source-raw fixture coverage". Current repo truth (confirmed via preflight ls + Glob in plan research): no `tests/fixtures/daily_brief_analytics/` directory or synthetic fixtures for forbidden/overly-long/parse/stale/path cases. The test_fastapi_analytics_daily_brief.py uses only inline tmp sample for the preserve test; no committed fixtures exercising the negative cases or providing no-mutation proof on original files. Per spec: open; we will add fixtures (synthetic markers only), copy-to-tmp tests, expanded coverage for states/path/bounds, and explicit pre/post hash proof that original fixture files on disk remain unchanged ("keep original file unchanged" + "no source file mutation proof").
  - FPR-016 (P3): "Preferences persistence is still an echo stub". **Already closed in current repo truth (Prompt 20)**. Evidence from preflight gap confirmation grep + prior P20 closeout (referenced in 00_PREFLIGHT history): real local JSON persistence exists (`_prefs_config_path()` using `PathPolicy()`, writes to `.../Application Support/.../analytics/ui_preferences.json`, `DEFAULT_PREFS`, `_load_prefs` (safe merge + fallback), `_save_prefs` (writes `schema_version: 1`), GET `/api/settings/preferences` returns effective values + `"note": "Preferences are local-first; persisted under Application Support (Prompt 20)." + guardrails`, PATCH applies and persists; `tests/test_fastapi_analytics_settings.py::test_preferences_get_and_patch` asserts re-GET reflects the patch (theme change) with comment "# Prompt 20 FPR-016: real persist (re-GET reflects, schema present after save)". Per P24 explicit guidance ("If preferences persistence was deferred in Prompt 20, either implement it or explicitly classify it as non-blocking with UI honesty." and "When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily"): we document the evidence (grep hits, P20 closeout reference, code/test/response note) and classify as closed. No re-implementation of load/save/persist logic.
  - Prompt 23 dep met: ls during preflight listed `prompt-23-end-to-end-local-smoke-harness-closeout.md`; current HEAD log top is exactly the Prompt 23 commit message. Dependency satisfied: "Prompt 23 should be closed or explicitly waived with evidence."
  Gaps handled per current repo truth and P24 spec (014 to close; 016 documented closed).

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. `cd frontend && npm install` was executed with no flag (normal path). Output contained standard funding/audit advisory ("To address all issues (including breaking changes), run: npm audit fix --force") but the command succeeded cleanly with no errors requiring --legacy. Lockfile present and used. Consistent with prior prompts' "up to date... found 0 vulnerabilities" where applicable; here post-P23 devDep additions the audit note is expected but non-blocking. No --legacy-peer-deps used or required.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. 'analytics-ui' in optional-dependencies list; fastapi 0.136.3 present in venv; pyproject version 1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present (size ~261k, grown from P23 Vitest/RTL/jsdom/user-event additions); `npm install` ran against it without requiring legacy flag or reporting lock incompatibility.

## Additional Notes for Prompt 24

- Repository truth authoritative (per package rules). Implementation against current HEAD (2f06b841..., post-Prompt 23).
- Prompt 23 closeout + commit confirmed to exist (ls during preflight listed `prompt-23-end-to-end-local-smoke-harness-closeout.md`; current HEAD log top is the P23 message). Dependency satisfied.
- Prompt 24 scope strictly limited to the listed items: FPR-014 (expanded Daily Brief fixtures for no-source-raw coverage + tests + original-file preservation proof), FPR-016 (document-only as P20 closed; no rework), packaging/safety (plain npm install/lint/type/build proof without legacy; strengthen no-raw/no-secrets/no-writeback scans for frontend evidence + receipt; add app-level ErrorBoundary if absent using P22 ErrorState patterns for CM-friendly fallback; document environment defaults (DEFAULT_PREFS, DEFAULT_CONFIG) and failure states (7 STATE_LABELS + _compute_state from daily_brief service + prefs) via closeout + minimal surface note if needed). Per "when already fixed, document... do not rework".
- Guardrails (read-only, local-first, no writeback, no raw, advisory, construction-management-first labels, hide detailed → Admin, chat disabled, role guards fail-closed, local role dev simulation only) remain in force and will be re-confirmed in the per-prompt closeout. Risk notes observed: synthetic markers only in fixtures (no real secrets/raw); no mutation of user Obsidian vault (tests use tmp + copy of committed fixtures only); normal npm path.
- Dirty/untracked files (unrelated M, planning pkgs, .claude, .code-graph, root package-lock, launcher/scheduler untracked) will not be cleaned, overwritten, or staged. Only Prompt 24 deliverables will be added at commit.
- Preflight captured exact baseline + P23 dep confirmation + FPR-014 open confirmation + FPR-016 already-closed evidence (grep + P20 refs) for the closeout evidence.

## Next (Prompt 24)

With preflight complete and evidence appended (this section), proceed to the implementation steps in strict order per the attached plan: document FPR-016 as already closed (grep/evidence only, cite P20 closeout + current code/test/response note), add synthetic daily_brief_analytics fixtures (3-4 .md with FAKE/SYNTHETIC only + pre/post hash helper), expand tests/test_fastapi_analytics_daily_brief.py (copy-to-tmp, cover forbidden/long/parse/stale/path, mutation-proof asserts, keep prior tests green), create ErrorBoundary (P22 style fallback, CM text, reload, console only), wire it in main.tsx or routes.tsx, add/strengthen frontend_safety_scan + run plain npm install + lint/type/build (capture proof, no legacy), document env defaults/failures (quotes in closeout + least-change note), run full validation (6 listed pytest + ruff/mypy + frontend matrix + 06 greps + browser smoke per 07), record browser notes, create prompt-24 closeout (08 template), light arch update (176/169/178), selective commit with traditional title, emit *only* the commit summary+description at end. Follow surgical + repo-truth first + update evidence same prompt + only output commit at very end. Mark preflight-24 completed and advance todos.

## Prompt 25 Preflight Run (re-run in sequence after Prompt 24)

Date: 2026-06-07  
Branch: main  
HEAD: a6324e968089cfe1f93c868854473bba54d3fba2

## Baseline Commands Executed (re-run for Prompt 25)

All commands from `docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/02_REPO_TRUTH_PREFLIGHT.md` Baseline Commands were re-run (venv python prefix used per CLAUDE.md and prior prompt executions; npm install executed as specified).

Captured output (git/node/npm verbatim; python via .venv/bin/python; plus targeted confirmation for P24 dep, FPR-018 packaging status, and FPR-015 deferred note):

```
=== PROMPT 25 PREFLIGHT START ===
Sun Jun  7 05:24:55 EDT 2026
=== git status --short ===
 M config/config.example.yml
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-dry-run.json
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-index-proof.md
 M docs/evidence/construction-intelligence-phase-07a-data-quality/07-obsidian-output-preview.md
 M docs/evidence/construction-intelligence-phase-07a-data-quality/obsidian-data-quality-dry-run.json
 M docs/evidence/construction-intelligence-phase-08b-automation-hardening/safe-replay-execution-proof.json
 M docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker
 M docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json
 M frontend/package-lock.json
 M pyproject.toml
 M src/hb_assistant/cli/construction.py
 M src/hb_assistant/cli/main.py
 M src/hb_assistant/config/models.py
 M src/hb_assistant/construction/analytics/api.py
 M src/hb_assistant/source_refresh/orchestrator.py
?? .claude/
?? .code-graph/
?? docs/architecture/187-cross-platform-launcher-and-scheduler.md
?? docs/evidence/frontend-production-readiness-implementation/prompt-24-frontend-safety-scan-proof.json
?? docs/evidence/source-refresh/dev-launcher-proof.json
?? docs/evidence/source-refresh/dev-launcher-proof.md
?? docs/evidence/source-refresh/launcher-close-background-proof.json
?? docs/evidence/source-refresh/launcher-close-background-proof.md
?? docs/evidence/source-refresh/production-launcher-proof.json
?? docs/evidence/source-refresh/production-launcher-proof.md
?? docs/evidence/source-refresh/scheduled-source-refresh-closeout.json
?? docs/evidence/source-refresh/scheduler-catch-up-proof.json
?? docs/evidence/source-refresh/scheduler-install-proof.json
?? docs/evidence/source-refresh/scheduler-install-proof.md
?? docs/planning/HB_Auth_Onboarding_Implementation_Package/
?? docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/
?? docs/planning/HB_Local_Production_Launcher_Desktop_Shortcut_Implementation_Package/
?? package-lock.json
?? scripts/proofs/launcher_scheduler_evidence_proof.py
?? src/hb_assistant/cli/launcher.py
?? src/hb_assistant/cli/scheduler.py
?? src/hb_assistant/launcher/
?? src/hb_assistant/scheduler/
?? tests/test_launcher_scheduler.py
=== git branch --show-current ===
main
=== git rev-parse HEAD ===
a6324e968089cfe1f93c868854473bba54d3fba2
=== git log --oneline -n 30 ===
a6324e96 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 24: Local-first production hardening (FPR-014/016)
2f06b841 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 23: End-to-end local smoke harness (FPR-012/018)
69661507 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 22: UI kit, accessibility, responsiveness consolidation (FPR-011/013)
e078b8d7 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 21: Admin / Data Confidence polish (FPR-007)
a0989799 HB Construction Intelligence — Procore Multi-Project Sync Fix v1.0.1 — all-project sync no longer crashes on "multi"
13a75675 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 20: Settings and onboarding polish (FPR-004/005/010/016/017)
f93b26b1 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 19: My Items dashboard (FPR-002 polish)
9f866749 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 18: Projects portfolio and project dashboards (FPR-003/009)
b06bbcde HB Construction Intelligence — Unified Source-Refresh Orchestrator v1.0.0 — construction-agent refresh-sources
b87f1c1b HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 17: Today dashboard UX/content completion (FPR-008)
73cc61af HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 16: Route/API contract hardening and launch blockers (FPR-001/002/006)
be470af1 chore(scripts): add local MCP stdio launcher for second-brain integration
9708be56 chore(evidence): refresh phase 06–09 evidence bundles after validation baseline
4d902ce0 HB FastAPI Analytics Dashboard — CM-First Implementation Package 2026-06-06T09:59:17.223062+00:00 — Prompt 08 / UI-08: nav active-state CSS, lucide-react upgrade, architecture record 176
75cf9390 HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.5.1-phase-09-addendum-v2 — Daily Brief V2 packet top-level self-identification (packet_version)
cc694c41 HB FastAPI Analytics Dashboard — CM-First Implementation Package 2026-06-06T09:59:17.223062+00:00: align Today routes and local role
ec19ac0e HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.5.0-phase-09-addendum-v2 — Prompt 06: Closeout & handoff
ff92c1ce fix(validation): resolve 33 pre-existing test failures — V39 lifecycle classification, automation weekend-gate determinism, no-writeback scan
3fbb8319 HB FastAPI Analytics Dashboard — CM-First Implementation Package
8beeb069 HB FastAPI Analytics Dashboard — CM-First Implementation Package
6e552751 HB FastAPI Analytics Dashboard — CM-First Implementation Package (Prompt 14A)
91acef0b HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.4.0-phase-09-addendum-v2 — Prompt 05: V2 validation & golden fixtures
9429d10d HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.3.0-phase-09-addendum-v2 — Prompt 04: Obsidian output path & receipt policy
03914314 HB FastAPI Analytics Dashboard — CM-First Implementation Package (Prompt 13 / UI-13)
4aeeace7 HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.2.0-phase-09-addendum-v2 — Prompt 03: Rendering template rewrite
3965ccb0 HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.1.0-phase-09-addendum-v2 — Prompt 02: Record-level enrichment
900c32f5 HB FastAPI Analytics Dashboard — CM-First Implementation Package (Prompt 11 / UI-11)
8c2f21ba HB FastAPI Analytics Dashboard — CM-First Implementation Package (Prompt 10 / UI-10)
918f0d25 HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening v1.0.0-phase-09-addendum-v2 — Prompt 01: Daily Brief V2 packet contract
8a2afb1b HB FastAPI Analytics Dashboard — CM-First Implementation Package (Prompt 09 / UI-09)
=== .venv/bin/python -m pip show fastapi || true ===
Name: fastapi
Version: 0.136.3
...
=== .venv/bin/python -m pytest --version ===
pytest 9.0.3
=== pyproject probe (.venv python) ===
project.version= 1.3.0
optional-dependencies= ['analytics-ui', 'dev', 'mcp', 'retrieval', 'retrieval-local', 'second-brain']
=== cd frontend; node --version ===
v22.14.0
=== npm --version ===
10.9.2
=== cat frontend/package.json ===
{ "name": "frontend", ... (has "test", "vitest", "smoke:frontend" from P23) }
=== package-lock check ===
package-lock.json present (size: 261580 )
=== npm install (frontend) ===
... (normal run; advisory note on audit fix --force but no --legacy-peer-deps flag used)
=== confirm P24 closeout dep (ls evidence) ===
00_PREFLIGHT.md
...
prompt-24-local-first-production-hardening-closeout.md
=== confirm P24 commit in log ===
a6324e96 HB FastAPI Analytics Dashboard — CM-First Implementation Package — Prompt 24: Local-first production hardening (FPR-014/016)
...
=== quick confirmation FPR-018 packaged (runbook/harness presence) ===
runbook not yet (will be created in this prompt)
scripts/smoke-local.sh
scripts/smoke_local.py
=== quick FPR-015 deferred note (charts) ===
docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md
docs/evidence/frontend-production-readiness-implementation/prompt-18-projects-portfolio-and-dashboards-closeout.md
docs/evidence/frontend-production-readiness-implementation/prompt-21-admin-data-confidence-polish-closeout.md
=== PROMPT 25 PREFLIGHT END ===
Sun Jun  7 05:24:57 EDT 2026
```

(Note: bare python -m corrected to .venv/bin/python per CLAUDE.md. Results authoritative. Dep and gap confirmations performed as part of preflight run.)

## Required Preflight Decisions (re-answered for Prompt 25)

- **Is the working tree clean before implementation?**  
  No. Working tree has various M (mostly prior-phase evidence and unrelated source like cli/construction, analytics/api.py incidental, pyproject, frontend lock) + many ?? (planning packages, .claude, .code-graph, root package-lock, new launcher/scheduler untracked, source-refresh dev proofs, architecture 187 launcher doc). The A files for frontend-production-readiness (prompt-16 through prompt-24 closeouts + 00_PREFLIGHT + the new prompt-24 safety proof json) are present as artifacts. Per 02 "If Preflight Fails": inventory and do not overwrite unrelated. For Prompt 25 we will *only* create/edit docs: new `docs/runbooks/frontend-local-analytics-smoke.md`, updates to `README.md` and `frontend/README.md`, new `docs/evidence/frontend-production-readiness-implementation/INDEX.md` (or FINAL...), append to this 00_PREFLIGHT.md if needed, new prompt-25 closeout md, light updates to architecture .md(s). Selective git add only for these at commit time. (No behavior code changes except doc links/wiring.)

- **Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?**  
  Yes. Current HEAD (a6324e96...) is the Prompt 24 commit, far after the original audit baseline.

- **Are there new frontend/backend commits after the audit?**  
  Yes. The top commit (a6324e96) is the Prompt 24 landing ("Local-first production hardening (FPR-014/016)"). Prompt 24 closed FPR-014 (fixtures + mutation proof + tests) and documented FPR-016 (P20 closed). The gap targeted by Prompt 25 (FPR-018 final packaging) is addressed in this prompt via the consumable runbook + existing P23 harness; FPR-015 (charts) remains the main deferred P3.

- **Do any P0/P1 gaps appear already fixed?**  
  N/A (Prompt 25 is P3 packaging + docs).  
  - FPR-018 (P3): "End-to-end local smoke harness and runbook are not yet packaged". In repo truth the harness/scripts/smoke_local.py + .sh + vitest + safety greps existed from P23 (confirmed in preflight); the runbook + final index + updates to make it "new developer can follow from docs" + "fresh clone style" documented smoke + evidence index are created in this prompt. P24 dep met (ls showed prompt-24-*-closeout.md; log top is the P24 message).  
  - FPR-015 (P3): Charts readiness remains deferred (recharts in package but unused in src; noted in P18/P21/P22/P24 closeouts and 00_PREFLIGHT). No chart work in this packaging prompt.  
  - Prompt 24 dep met: ls during preflight listed `prompt-24-local-first-production-hardening-closeout.md` (and the safety proof json); current HEAD log top is exactly the Prompt 24 commit message. Dependency satisfied.  
  Gaps handled per current repo truth and P25 spec (018 packaged via docs/runbook; 015 noted deferred).

- **Does `npm install` complete without `--legacy-peer-deps`?**  
  Yes. `cd frontend && npm install` was executed with no flag (normal path). Command succeeded (advisory note on "npm audit fix --force" present but non-blocking, as in prior prompts). No --legacy-peer-deps used or required.

- **Does the FastAPI optional dependency group still include the dashboard dependencies?**  
  Yes. 'analytics-ui' in optional-dependencies list; fastapi 0.136.3 in venv; pyproject version 1.3.0.

- **Does the frontend lockfile appear current relative to `package.json`?**  
  Yes. package-lock.json present (size ~261k); `npm install` ran against it without legacy flag or incompatibility.

## Additional Notes for Prompt 25

- Repository truth authoritative (per package rules). Implementation against current HEAD (a6324e96..., post-Prompt 24).
- Prompt 24 closeout + commit confirmed to exist (ls listed it and the safety proof; log top is the P24 message). Dependency satisfied.
- Prompt 25 scope strictly limited to packaging FPR-018 (create the consumable runbook that references the P23 scripted harness + two-terminal visual per 07, plus "fresh clone style" documented steps), final docs hygiene (root + frontend README updates with links and honest "implemented vs planned" language), creation of evidence index (Prompt 16-25 sequence, artifacts, gaps status with FPR-015 deferred, pointers), light arch cross-refs, prompt-25 closeout, doc link/path checks + stale-claim grep + "fresh clone style" smoke simulation as far as local env allows (capture labeled), no behavioral code changes beyond doc links/wiring. Per "when already fixed, document... do not rework" and "distinguish current behavior from planned/future".
- Guardrails (read-only, local-first, no writeback, no raw, advisory, construction-management-first labels, hide detailed → Admin, chat disabled, role guards fail-closed, local role dev simulation only) remain in force and will be re-confirmed in the per-prompt closeout. All new docs will re-state them. Risk notes observed: do not claim production readiness without evidence; do not bury blockers.
- Dirty/untracked files (unrelated M from prior phases, planning pkgs, .claude, .code-graph, launcher/scheduler untracked, source-refresh proofs, root package-lock) will not be cleaned, overwritten, or staged. Only Prompt 25 deliverables (docs/runbook/index/closeout + light arch + 00_PREFLIGHT append) will be added at commit.
- Preflight captured exact baseline + dep confirmation for the closeout evidence. FPR-018 runbook created in this prompt; harness from P23 confirmed present.

## Next (Prompt 25)

With preflight complete and evidence appended (this section), proceed to the implementation steps in strict order per the attached plan: create the frontend-local-analytics-smoke.md runbook (prereqs, one-command scripted path via P23 harness, two-terminal visual per 07 checklist with roles + no-404/console + /chat inaccessible, Settings/Daily Brief/Admin flows, capture instructions, known limitations incl. FPR-015 charts deferred, guardrails), update frontend/README.md (add runbook link + honest future note), update root README.md (concise pointer to local dashboard + runbook), create evidence INDEX.md (16-25 list + artifacts + gaps + pointers), light arch updates (176 primary + others), produce prompt-25 closeout (08 template), final verification (doc link/path checks + fresh-clone smoke sim commands + final stale-claim grep), selective commit with traditional title, emit *only* the commit summary+description at end. Follow surgical + repo-truth first + update evidence same prompt + only output commit at very end. Mark preflight-25 completed and advance todos.

