# 199. Frontend Chrome Header Owns Page Titles + Coupled My Dashboard Navigation (Addendum)

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package (P09 addendum)

## Decision

The AppShell chrome header (the top `<header>` bar) is now the owner of the active page/route title. The static brand text ("Personal Assistant", post the prior rebrand of "HB Analytics") is removed from the header and replaced by a dynamic value resolved per route.

Implementation:

- Centralized title metadata:
  - `frontend/src/navigation/navigationModel.ts`: NavItem extended with optional `children?: NavItem[]`; `PRIMARY_NAV` restructured so "My Dashboard" (route `/today`) is the parent with nested `{ label: 'Today', route: '/today' }` child (Projects and My Items remain flat siblings); `isActive` and icon mapping extended; new named export `getRouteTitleForPath(path)` encapsulates the prior case logic (Today, Projects, All Projects • Meetings/Field/Cost, Project, My Items, Data Health, Settings, Get Started, with "Personal Assistant" fallback).
  - `frontend/src/app/routes.tsx`: declarative `handle: { title: '...' }` metadata attached to the primary routes (today, projects, my-items, admin, settings, get-started). Dynamic segments (e.g. `/projects/:projectKey`, `/projects/all/*` variants) continue to be enriched by the path-based resolver.

- Chrome consumption (AppShell):
  - `useMatches()` + reverse/find for the deepest handle title (if present) with fallback to `getRouteTitleForPath(location.pathname)`.
  - The resolved title is rendered in the header bar: `<div className="font-medium">{headerTitle}</div>`.
  - `<PageHeader title=... />` (and its import) removed from the shell.
  - A single accessible page heading is provided via `<h1 className="sr-only">{headerTitle}</h1>` inside `<main id="main">` (before the Outlet/children). The generic advisory previously inside PageHeader is no longer duplicated in the body (the persistent footer carries the equivalent language).

- Body cleanup (PrimaryPageLayout and callers):
  - `PrimaryPageLayout`: `title` and `subtitle` removed from props type and render block. The component remains a lightweight content wrapper (actions/status row + children). Comment updated to record that the chrome header now owns titles and the sr-only h1 + card/section h3s provide a11y structure.
  - All five primary page call sites updated to stop passing `title=` / `subtitle=` (TodayPage, ProjectsPage, MyItemsPage, SettingsPage, ProjectDashboardPage). Local `title` computation in ProjectDashboardPage is retained only for its internal loading label (not passed to layout).

- Coupled navigation (per addendum requirement):
  - "My Dashboard" parent + nested "Today" child introduced in the model and MainNavigation renderer (indented `ul.ml-6` children under parent Link). No URL changes (Today remains `/today`; title for that path remains "Today"). The active title resolver and nav active states support the new parent/child structure. This satisfies the explicit coupling note that the title system must support the new parent and nested Today view.

- Sub-pages unaffected in body structure (ProjectMeetingsPage, ProjectFieldOperationsPage, ProjectCostTimePage, DataHealthPage, GetStartedPage) continue to render their own content/subnav; they now receive identity from the chrome title + sr-only h1.

- Tests adjusted:
  - AppShell.test: new assertion that the chrome header text reflects the current route (e.g. "Today", "Projects") and that the static brand is no longer the header value.
  - Page tests + DashboardPrimitives.test: comments refreshed to describe chrome ownership and absence of body duplicate labels; removed/adjusted `findByText` / `getByText` expectations that targeted the removed Primary title labels (e.g. the "Settings" body label wait in SettingsPage.test now waits for first panel content "Account Connections"; primitives test no longer passes or asserts the dropped title/subtitle). `arrayContaining` heading checks remain valid (sr-only h1 text + card/section h3s).

No changes were made to:
- The document `<title>` (remains the app name "Personal Assistant").
- Footer advisory copy.
- Sub-page internal section/card titles or empty-state labels.
- Any "analytics" strings, planning/evidence, or broader renames.

Post-change obligations executed:
- Architecture documentation updated (`docs/architecture/199-...`).
- Exact verification block from the prompt executed (cd frontend; the four `npm run` commands + the two `grep -R` commands exactly as listed).
- Traditional commit with manifest title "frontend-ui-ux-shell-layout-implementation-package" and version "2026-06-07 / 0.0.0"; only the addendum deltas staged.
- Agent final output is solely the commit summary + description.

## Rationale

Prior work (P01–P09 + the immediate rebrand addendum) had already removed most duplicate high-level headings and telemetry jargon, and established PrimaryPageLayout titles as visual (non-h) labels with the canonical h1 coming from shell PageHeader. The addendum prompt required the chrome header itself (the persistent top bar) to be the visible owner of the active page title, eliminating the last static brand text ("Personal Assistant") from the routed-page header area and removing the duplicate body title chrome entirely. This yields:
- One clear, route-sensitive title in the chrome.
- No visual double-header on primary/secondary pages.
- Page bodies starting directly with dashboard/content (status/actions + cards/sections).
- Exactly one accessible page-level heading per route (sr-only h1) plus the existing semantic h3s inside content.

The coupled navigation requirement was satisfied by extending the existing declarative NavItem model and renderer with a parent/child structure ("My Dashboard" > Today) without altering routes or URLs, keeping the active title system (getRouteTitleForPath + handles) as the single source for both chrome text and the sr-only h1.

Declarative route handles + the path fallback keep titles co-located with navigation while gracefully supporting dynamic segments.

All changes are source-only UI structure/copy; behavior, data, auth, and backend are untouched.

## Guardrails

- Read discipline strictly observed: exploration and pre-edit reads limited to `frontend/src/**` (via Grep with `path: "frontend/src"`, Glob patterns starting `frontend/src/**`, and Read only on the actual edit-target source files). Zero Read or Grep targeting `docs/planning/**` (phase README, any addendum_*.md, prompts/, or the attached rebrand plan). Readonly Shell only for git baseline/status and the final verification commands.
- Scope: only the listed files + the new 199 ADR. No html title, no footer, no sub-page body rewrites, no broader renames.
- a11y: single h1 (sr-only) per route + preserved h3 card/section headings; landmarks and skip link untouched.
- Tests: chrome title presence asserted; stale body-label waits and asserts removed or retargeted; no new runtime behavior tests required.
- Verification: the prompt's exact block (`npm run lint && typecheck && build && test` followed by the two `grep -R` lines) was executed and captured. Pre-existing non-blocking items (e.g. the long-standing ErrorBoundary eslint-disable warning) noted as unrelated.
- Commit hygiene: only the addendum deltas were staged (nav model, main nav, routes, AppShell, PrimaryPageLayout, the five pages, the six test files, and 199 ADR). Traditional message format matching prior P09 commits on the branch (manifest title + version, bullets, Safety paragraph).
- Safety: purely frontend display hierarchy, title resolution, and navigation model tweaks. No external calls, tokens, writes, auth changes, or data flows. The prior copy-regression harness (`npm run copycheck`) and existing forbidden-term tests continue to protect the surface.

This addendum closes the explicit "Chrome Header Owns Page Titles" objective and the coupled "My Dashboard navigation" requirement while preserving all prior P0/P1 invariants from the parent package.

Evidence of the run (full command output) lives with the commit and operator logs. Future shell or navigation work must keep the chrome as the title owner and must update `getRouteTitleForPath` + route handles + MainNavigation children rendering for any new top-level or nested views.

## Refinement (this pass)

Per post-addendum clarification, the navigation model was adjusted so that "My Dashboard" renders the former "My Items" work-queue page content, "My Items" no longer appears as a nav option, and "Today" does not appear in the sidebar at all (Today content is reached via in-page links from the My Dashboard view and from other surfaces).

- `frontend/src/navigation/navigationModel.ts`: `PRIMARY_NAV` reduced to flat two-item list: `[{ label: 'My Dashboard', route: '/my-dashboard' }, { label: 'Projects', route: '/projects' }]`. `children` support and prior nesting removed for this model. `getRouteTitleForPath` updated to return 'My Dashboard' for paths starting with `/my-dashboard` or legacy `/my-items`; 'Today' continues to resolve for `/today`. CONTEXTUAL_ONLY comment and related wording cleaned.
- `frontend/src/app/routes.tsx`: Added clean `path: 'my-dashboard'` entry rendering `<MyItemsPage />` with `handle: { title: 'My Dashboard' }`. Retained `path: 'my-items'` (same element, legacy alias; its handle left as-is but resolver overrides title). `path: 'today'` retained unchanged (TodayPage remains directly addressable). `StartupRedirect` (and its JSDoc + inline comments) changed from default `/today` to `/my-dashboard`; the root comment and "otherwise → /today" references updated. Root comment re Get Started not in PRIMARY_NAV left as accurate.
- `frontend/src/layouts/AppShell.tsx`: Sidebar comment updated from "(Today / Projects / My Items)" to "(My Dashboard / Projects)".
- Label / link hygiene (minimal, only the two "My Items" destination labels): `MyItemsPage.tsx` + its test updated "Loading My Items" → "Loading My Dashboard". `TodayPage.tsx` Action Items empty-state link changed `to="/my-items"` + "Open My Items" → `to="/my-dashboard"` + "Open My Dashboard". `ProjectMeetingsPage.tsx` small link changed from "/my-items" + "See My Items..." → "/my-dashboard" + "See My Dashboard...". All "Open Today" / "Back to Today" links from non-nav surfaces left pointing at `/today` (legitimate in-page reachability).
- Architecture: this refinement section appended. All prior invariants (chrome owns titles, single sr-only h1 per route, no duplicate body titles, Projects unaffected, legacy paths non-dead) preserved.

Final model summary:
- Primary nav: My Dashboard (first) | Projects
- `/my-dashboard` (and legacy `/my-items`) → MyItemsPage content (work queue); chrome title = "My Dashboard"
- `/today` (and internal links) → TodayPage; Today not in sidebar
- `/` → StartupRedirect → /my-dashboard (non-first-time)
- `/today` and `/my-items` continue to function (alias/legacy)
- Today navigation from My Dashboard page (and reciprocal surfaces) provides the in-page access path.

Post-execution: architecture updated; exact verification block run; only refinement deltas staged for traditional commit (manifest title + version 2026-06-07 / 0.0.0); final agent output is solely the summary + description.

## Generalization (this pass)

Per follow-up request, the redundant top actions bar (duplicate of the primary action already rendered inside the status row) was removed from the remaining primary dashboard pages, generalizing the prior My Dashboard polish.

- `frontend/src/pages/TodayPage.tsx`: removed `actions={<CheckDataHealthLink />}` from the success PrimaryPageLayout (import retained for error state and one inner TodaySectionEmpty action). `status={<TodayStatusRow ... />}` remains; TodayStatusRow already renders the "Check Data Health" link, so the status row now sits directly under the "Today" chrome header with no duplicate bar.

- `frontend/src/pages/ProjectsPage.tsx`: removed `actions={<AllProjectsLink label="Open All Projects" />}` (import retained for two inner SectionCard actions). `status={<ProjectStatusRow ... />}` remains (provides the connections link). "Open All Projects" affordance remains discoverable inside the "All Projects" section card on the page body.

- `frontend/src/pages/ProjectDashboardPage.tsx`: removed `actions={<ProjectConnectionsLink />}` (import retained for the "No project overview yet." EmptyState). Applies to both the aggregated "all" view and per-project `/:projectKey` detail routes. `status={<ProjectStatusRow ... />}` supplies the link.

- `frontend/src/components/layout/DashboardPrimitives.test.tsx`: first test description and comments refreshed to record that primary pages no longer supply a duplicative top actions prop (status rows own the controls) while the primitive continues to support the dual (status + actions) pattern for contract coverage / future use.

- No changes to PrimaryPageLayout (conditional already tightened in prior polish), the *StatusRow or *Actions components (they are the source of truth for the controls), MyItemsPage (already clean), SettingsPage (bare layout with no status/actions), or sub-pages / secondary surfaces.

- Tests: all link expectations ("Check Data Health", "Review project connections in Settings", "Open All Projects", etc.) continue to pass because the elements remain in the DOM via status rows or scoped inner content/empty states. 51/51 tests green.

- Architecture: this generalization section appended. All prior invariants (chrome owns titles + dynamic resolution, single sr-only h1 per route, no duplicate body titles, copy-regression harness, legacy paths, read discipline) preserved. Pre-existing lint warning (ErrorBoundary) noted as unrelated.

- Verification: exact block executed (cd frontend; the four npm commands; the three greps with || true); lint clean (0 errors), type/build clean, tests pass; greps show expected patterns only.

- Commit: only the generalization deltas (three pages + primitives test + this ADR append) staged; traditional commit with manifest title + version; final output solely summary + description.

This closes the "remove the redundant row from all pages" objective while keeping the design where status rows are the canonical place for the primary page-level action links directly under the chrome header.