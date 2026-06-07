# 08 Production Readiness Gap Register

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


## FPR-001 — Project tab pages can crash because frontend treats object read models as arrays

- Severity: P0
- Affected area: Projects
- Repo evidence: ProjectMeetingsPage, ProjectFieldOperationsPage, and ProjectCostTimePage assign items=(data?.items || data || []) and call items.slice(); backend project tab endpoints return objects with metric_cards/attention_items/sections, not arrays.
- Why it matters: Blocks core Projects usability for Meetings, Field Operations, and Cost & Time; local browser route can render a TypeError even while backend API returns 200.
- Recommended fix: Normalize project tab responses in a shared adapter; render metric_cards and attention_items; or add backend items arrays. Add tests that each route renders when backend returns object envelopes.
- Prompt placement: Prompt 16
- Tests / validation: npm run typecheck, npm run build, browser smoke /projects/all/meetings /field-operations /cost-time, pytest dashboard read models

## FPR-002 — My Items page calls unimplemented backend subroutes

- Severity: P1
- Affected area: My Items / API alignment
- Repo evidence: Frontend calls /api/my-items/action-items, /meetings, /correspondence, /files, /followed-projects; backend route inventory exposes only /api/my-items.
- Why it matters: Creates failed React Query requests and noisy console/network errors; undermines the user-specific work queue.
- Recommended fix: Either add backend compatibility section endpoints derived from build_my_items() or refactor frontend to use the aggregate /api/my-items only.
- Prompt placement: Prompt 16
- Tests / validation: pytest app shell openapi path assertion, new pytest my-items section routes or updated frontend no-call test, browser smoke /my-items no 404s

## FPR-003 — Projects portfolio selector does not consume backend project_keys

- Severity: P1
- Affected area: Projects
- Repo evidence: ProjectsPage expects portfolio.projects or portfolio.items array; backend build_projects_portfolio returns project_keys, metric_cards, attention_items, and sections.
- Why it matters: Individual projects may not appear even when backend has project_keys, so Projects feels empty/demo-like.
- Recommended fix: Adapt ProjectsPage to build project cards from project_keys and metric_cards, or update backend to emit a projects array with key/name/freshness/status.
- Prompt placement: Prompt 18
- Tests / validation: component/unit test for project_keys response, browser smoke /projects with seeded project_keys

## FPR-004 — Settings page still exposes raw JSON/debug response panels

- Severity: P1
- Affected area: Settings / UX / sensitive posture
- Repo evidence: SettingsPage renders multiple <details><summary>Raw response</summary><pre>{JSON.stringify(...)}</pre></details> blocks.
- Why it matters: Conflicts with polished local-first app direction and can make Settings feel like a backend test harness.
- Recommended fix: Replace raw JSON panels with concise status cards and optional admin-only redacted diagnostics routed to Admin/Data Confidence.
- Prompt placement: Prompt 20
- Tests / validation: grep no Raw response in SettingsPage, frontend smoke settings load buttons, safe serialization tests remain green

## FPR-005 — Daily Brief currentState expression has precedence bug

- Severity: P1
- Affected area: Settings / Daily Brief
- Repo evidence: SettingsPage computes currentState with detectResult?.state || status?.state || status?.config?.enabled === false ? "not_configured" : undefined.
- Why it matters: Truthy status can incorrectly display not_configured, confusing first-run setup and daily brief confidence.
- Recommended fix: Use explicit parentheses and helper function: if disabled -> not_configured; else detectResult.state ?? status.state. Add test around configured_waiting and brief_available states.
- Prompt placement: Prompt 20
- Tests / validation: npm run typecheck, Daily Brief state unit test, manual Settings detect states

## FPR-006 — BrowserRouter pages contain hash-style links

- Severity: P1
- Affected area: Navigation
- Repo evidence: TodayPage uses href="#/settings" and SettingsPage uses href="#/today" despite createBrowserRouter route model.
- Why it matters: Creates broken or confusing navigation under the Vite BrowserRouter app.
- Recommended fix: Replace with <Link to="/settings"> and <Link to="/today">.
- Prompt placement: Prompt 16
- Tests / validation: npm run typecheck, browser smoke clicking Today/Settings links

## FPR-007 — Admin page does not present role-denied state clearly

- Severity: P1
- Affected area: Admin / Data Confidence
- Repo evidence: AdminDataConfidencePage fires admin-only queries and renders Loading… for missing data; backend requires admin role.
- Why it matters: With default operator local role, Admin may look broken instead of role-restricted.
- Recommended fix: Detect 403 errors and render a clear “Admin role required” state with local role selector guidance.
- Prompt placement: Prompt 21
- Tests / validation: browser smoke admin as operator/admin, React Query error state test, pytest admin 403 remains

## FPR-008 — Today dashboard is missing explicit required sections

- Severity: P1
- Affected area: Today UX
- Repo evidence: TodayPage renders Important Today, Daily Brief, Today’s Meetings, What Changed, Action Items, and Portfolio Signals; required explicit Documents/Correspondence and Cost/Change/Time sections are not first-class.
- Why it matters: Today does not yet fully match the construction command-center brief.
- Recommended fix: Split Portfolio Signals into Cost / Change / Time Signals and Documents & Correspondence Worth Reviewing; keep data confidence compact.
- Prompt placement: Prompt 17
- Tests / validation: frontend route smoke /today, copy/label regression test, no raw calendar body/join URL scan

## FPR-009 — Hardcoded freshness/confidence values remain on project pages

- Severity: P2
- Affected area: Projects UX
- Repo evidence: ProjectFieldOperationsPage hardcodes stale/19 minutes; other project subpages hardcode fresh/source_backed.
- Why it matters: Stale/fresh confidence becomes misleading when backend returns actual freshness/confidence.
- Recommended fix: Always bind badges to backend freshness/confidence_summary; default to unknown only when absent.
- Prompt placement: Prompt 18
- Tests / validation: component tests for freshness rendering, browser smoke with stale/fresh fixtures

## FPR-010 — Settings still feels like backend controls rather than onboarding

- Severity: P2
- Affected area: Settings / Product fit
- Repo evidence: Settings uses Load buttons, sample admin rate limit, “sent (stub)” copy, and fragmented cards.
- Why it matters: Increases friction and reinforces engineering-console feel.
- Recommended fix: Convert to guided Account Connections, Project Connections, Daily Brief, Preferences sections with preview→save cards and clear next actions.
- Prompt placement: Prompt 20
- Tests / validation: UX smoke path new user setup, no stub text grep, settings backend tests

## FPR-011 — alert() error handling remains in Settings

- Severity: P2
- Affected area: Frontend error handling
- Repo evidence: SettingsPage catch blocks still call alert() for configure, instructions, validate, and detect failures.
- Why it matters: Alerts interrupt workflow and feel unpolished.
- Recommended fix: Use shared inline ErrorState/Toast-like component with retry actions.
- Prompt placement: Prompt 22
- Tests / validation: grep no alert(, manual failure smoke

## FPR-012 — No frontend test harness found

- Severity: P2
- Affected area: Testing / Validation
- Repo evidence: GitHub search returned no Vitest, Playwright, or Testing Library usage in frontend.
- Why it matters: Regression risk is high for route/API alignment and browser launch.
- Recommended fix: Add Vitest + React Testing Library for components/adapters and Playwright or scripted browser smoke for local routes.
- Prompt placement: Prompt 23
- Tests / validation: npm run test, npm run smoke:frontend, npm run build

## FPR-013 — Responsive/accessibility baseline is incomplete

- Severity: P2
- Affected area: Styling / UI kit
- Repo evidence: AppShell uses fixed sidebar; CSS focus-visible covers anchors/buttons but not inputs/selects; mobile navigation is not evident.
- Why it matters: Local-first desktop is primary, but production-ready polish still needs keyboard and smaller-window behavior.
- Recommended fix: Add responsive sidebar collapse, focus styles for inputs/selects, skip link, semantic regions, form labels, and accessible loading/error states.
- Prompt placement: Prompt 22
- Tests / validation: axe/manual a11y smoke, keyboard navigation smoke, responsive viewport smoke

## FPR-014 — Daily Brief latest endpoint returns bounded Markdown content; needs explicit no-source-raw fixture coverage

- Severity: P2
- Affected area: Daily Brief / Safety
- Repo evidence: DailyBriefService latest/presentation returns Markdown content and sections from local file; tests assert preservation and no forbidden markers but not all source-raw scenarios.
- Why it matters: The daily brief is user-authored external Markdown, but safety claims should be explicit for local-first production.
- Recommended fix: Add fixtures for forbidden content, overly long files, parse warnings, stale files, and path display; keep original file unchanged.
- Prompt placement: Prompt 24
- Tests / validation: pytest daily brief expanded fixtures, no source file mutation proof

## FPR-015 — Chart readiness dependency exists but chart UX is not implemented

- Severity: P3
- Affected area: UI kit / Future enhancement
- Repo evidence: Recharts is declared but pages use cards/lists only.
- Why it matters: Trend surfaces will eventually need compact visuals, but not a launch blocker.
- Recommended fix: Defer until route contracts are stable; add chart card only for validated metrics.
- Prompt placement: Post-production enhancement
- Tests / validation: visual smoke, data contract tests

## FPR-016 — Preferences persistence is still an echo stub

- Severity: P3
- Affected area: Settings / Preferences
- Repo evidence: /api/settings/preferences returns hardcoded defaults; PATCH echoes applied payload.
- Why it matters: Theme is locally persisted in frontend, but default landing/followed projects/preferences are not yet durable through backend.
- Recommended fix: Persist preferences to local Application Support JSON with schema/version and safe validation.
- Prompt placement: Prompt 20 or 24
- Tests / validation: pytest preferences roundtrip, browser reload persistence

## FPR-017 — Project keyword UI is informational only

- Severity: P3
- Affected area: Settings / Project Matching
- Repo evidence: Settings keywords card tells user to manage per-project /keywords routes rather than providing add/edit/disable UI.
- Why it matters: Project matching setup remains developer-facing and incomplete for non-technical use.
- Recommended fix: Add project keyword management UI with project selector, active/disabled/excluded lists, preview explain, and safe validation.
- Prompt placement: Prompt 20 or later
- Tests / validation: pytest keyword routes, frontend keyword CRUD smoke

## FPR-018 — End-to-end local smoke harness and runbook are not yet packaged

- Severity: P3
- Affected area: Documentation / Operations
- Repo evidence: Prompt requires backend on 8000 and frontend on 5173 smoke; current repo has scripts but no confirmed E2E smoke harness in frontend.
- Why it matters: Production-ready local-first use needs repeatable launch validation.
- Recommended fix: Create one command/scripted runbook for install, backend start, frontend start, route smoke, no 404/console errors, and role switching.
- Prompt placement: Prompt 25
- Tests / validation: run documented smoke from clean checkout, capture evidence
