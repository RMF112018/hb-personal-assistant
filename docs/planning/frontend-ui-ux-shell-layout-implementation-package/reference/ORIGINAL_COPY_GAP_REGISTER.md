# Gap Register

## COPY-P0-001 — Local dev role selector is visible in normal app chrome

- Severity: P0
- Area: App shell / production chrome
- Evidence: frontend/src/layouts/AppShell.tsx lines 63-80 render 'Local dev role — not production auth' plus Viewer/Operator/Admin selector.
- Why it matters: Normal users should not see implementation-role simulation or auth disclaimers in the primary header.
- Recommended fix: Move role selector behind an explicit development-only flag or developer panel; remove from production shell. Ensure default production UI has no local role copy.
- Prompt placement: Prompt C01

## COPY-P1-002 — Disabled Chat remains visible as a support-nav item

- Severity: P1
- Area: Navigation / chat exposure
- Evidence: frontend/src/navigation/navigationModel.ts lines 24-26 define Chat as disabled; SupportNavigation.tsx lines 25-36 renders it with '(disabled)'.
- Why it matters: Product direction says chat is future/stub-only and no active or accessible in-app chat interface should be visible to users.
- Recommended fix: Remove disabled chat nav item from visible UI; keep route absent and optionally document chat disabled in developer docs only.
- Prompt placement: Prompt C01

## COPY-P0-003 — Frontend does not consume new normalized auth/readiness contract

- Severity: P0
- Area: Settings / auth onboarding
- Evidence: Backend now exposes /api/onboarding/readiness and /api/settings/connections/* routes, but frontend/src/lib/api.ts only exposes legacy Settings functions through /api/settings/accounts/projects/sources/keywords and lacks Prompt A client helpers.
- Why it matters: After Prompt A, the frontend should stop presenting old status loaders and use end-user account readiness states for Microsoft 365, Procore, project connections, approvals, and data quality.
- Recommended fix: Add typed client helpers for readiness, accounts, auth refresh, normalized project preview/save/list, admin approval, data-quality summary/detail; update Settings and shell to consume them.
- Prompt placement: Prompt C02

## COPY-P0-004 — Settings still exposes prompt IDs, loader actions, raw-panel remnants, and backend workflow labels

- Severity: P0
- Area: Settings / connection management
- Evidence: SettingsPage.tsx includes labels such as 'Account Connections (Prompt 14B)', 'Load Accounts Status', 'Project Connections (Prompt 14B)', 'Load Projects', 'Source Scope (Prompt 14B)', 'Load Source Scope', 'raw panels removed per FPR-004', and 'preview→save (14A)'.
- Why it matters: Settings is the onboarding gateway; internal labels make it feel unfinished and can confuse non-engineering users.
- Recommended fix: Rewrite Settings as guided Account Connections, Project Connections, Daily Brief, Preferences, and Admin Approval flows with plain actions and no prompt IDs or raw/debug language.
- Prompt placement: Prompt C03

## COPY-P1-005 — Keyword management exposes project keys, JSON.stringify output, Explain/List debug surfaces

- Severity: P1
- Area: Settings / keyword management
- Evidence: SettingsPage.tsx lines 269-298 show 'Keyword Management (per project)', 'Project key', 'Load List', 'Explain', and render JSON.stringify output slices.
- Why it matters: Project matching needs a business-facing management surface, not a developer/debug panel.
- Recommended fix: Replace with project picker, keywords table/list, add/remove actions, and plain preview wording; no JSON output in the normal UI.
- Prompt placement: Prompt C03

## COPY-P1-006 — Today still includes backend/startup and read-model copy

- Severity: P1
- Area: Today
- Evidence: TodayPage.tsx lines 38-43 tell the user to start FastAPI/uvicorn; line 177 mentions composed read models and source/sync/evidence; Daily Brief advisory names state machine values.
- Why it matters: Today is the primary command center and must not read like an engineering test harness.
- Recommended fix: Replace technical failure states with end-user guidance: 'This section could not be loaded', 'Check Data Health', 'Connect sources', 'Last updated'. Simplify Daily Brief states.
- Prompt placement: Prompt C04

## COPY-P1-007 — Admin page still uses engineering telemetry labels

- Severity: P1
- Area: Admin / Data Health
- Evidence: AdminDataConfidencePage.tsx lines 23-30 use Source / Sync Health, Workflow / Job Health, Evidence / Guardrail Health, Retrieval / AI Quality, Permissions / Governance, Data Completeness / Coverage; lines 56-58 instruct use of local dev role selector.
- Why it matters: Admin can retain detail but should translate system health into business-readable labels and actions.
- Recommended fix: Rename to Source Updates, Background Tasks, Safety Checks, Answer Quality, Access & Permissions, Data Coverage; hide technical diagnostics behind disclosure; replace local-role instructions with production access language.
- Prompt placement: Prompt C05

## COPY-P1-008 — Core pages still mention source systems, Admin approvals, domain-nav implementation constraints, and diagnostics

- Severity: P1
- Area: My Items / Projects
- Evidence: MyItemsPage.tsx lines 86-156 and ProjectsPage.tsx lines 43-74 contain source-system/setup/admin language; ProjectDashboardPage.tsx lines 48-55 mention contextual tabs, read models, Admin Data Confidence, and no top-level domain navs.
- Why it matters: Core work surfaces should explain what the user can do, not how the app is architected.
- Recommended fix: Use simple empty states and helper copy: 'Connect Microsoft 365/Procore in Settings', 'Waiting for first update approval', 'No items need attention'. Move architecture constraints to docs/tests.
- Prompt placement: Prompt C04

## COPY-P2-009 — ErrorState renders raw backend error messages and HTTP status text

- Severity: P2
- Area: Shared errors / API client
- Evidence: api.ts lines 54-64 builds errors from HTTP status/detail; ErrorState.tsx lines 3-11 displays message directly.
- Why it matters: Raw 403/404/backend details degrade trust and expose internal state vocabulary.
- Recommended fix: Introduce user-safe error mapping with optional admin/developer details disclosure; never show route names/status codes in normal views.
- Prompt placement: Prompt C06

## COPY-P2-010 — Vite starter App.tsx remains in source tree with React/Vite demo copy

- Severity: P2
- Area: Unused starter source
- Evidence: frontend/src/App.tsx lines 21-64 include 'Edit src/App.tsx', HMR, Vite/React docs, Count is, and community links, although main.tsx uses AppRouter.
- Why it matters: Even if unused, production scans and future imports can surface demo copy; it is repo clutter.
- Recommended fix: Delete or replace unused App.tsx/App.css/assets starter copy after confirming no imports, or update to a harmless redirect/test-only placeholder.
- Prompt placement: Prompt C07

## COPY-P2-011 — Daily Brief still exposes external Markdown, MCP, scheduled prompt, 7 states, parse/state language

- Severity: P2
- Area: Daily Brief
- Evidence: SettingsPage.tsx lines 229-256 and 560-599; TodayPage.tsx lines 92-107 expose Markdown/presenter workflow and state names.
- Why it matters: The intended user-facing concept is a Daily Brief, not a Markdown/MCP pipeline.
- Recommended fix: Keep advanced setup behind disclosure; normal UI says folder, brief file, last updated, ready/stale/missing, and source brief. Avoid 'MCP' unless advanced instructions are opened.
- Prompt placement: Prompt C03/C04

## COPY-P2-012 — No dedicated frontend display-copy forbidden-term scan is visible in current client code

- Severity: P2
- Area: Regression safety
- Evidence: Current UI still contains prompt IDs, local dev role, raw panels removed text, JSON.stringify outputs, backend terms, read-model text, and Vite starter copy.
- Why it matters: Manual cleanup will regress without automated guardrails.
- Recommended fix: Add a copy audit script/test with allowlists for docs/tests/dev-only files and forbidden terms for production-rendered TSX/TS files.
- Prompt placement: Prompt C08
