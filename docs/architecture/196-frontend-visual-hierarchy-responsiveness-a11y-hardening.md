# 196. Frontend Visual Hierarchy, Responsiveness, and Accessibility Hardening

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package (P08)

## Decision

- PrimaryPageLayout title is rendered as a non-heading visual label (div.text-lg.font-semibold) with subtitle/actions/status bar retained for scannability and density. The canonical h1 is provided exclusively by the shell PageHeader (always present in AppShell). Cards and sections continue to use h3 (DashboardCard direct h3; SectionCard via .section-title).

- .card base (p-4 rounded-lg border surface/border via CSS vars) enhanced with var-backed subtle shadow (--hb-card-shadow, stronger on dark) for calm elevation. Added transitions and :hover { border-accent; increased shadow } to .card, DashboardCard, SectionCard, and MyWorkQueueItem for consistent interactive feedback. ProjectCard already aligned.

- Explicit .nav-item:focus-visible (outline accent) added alongside global a/button:focus-visible (outline + offset). Existing custom focusables (e.g. DataQuality trigger with tabIndex + ring + group-focus-within tooltip) preserved. Keyboard-visible states cover nav, cards, badges (when buttons/links), and actions.

- DashboardGrid provides responsive column classes (all variants start grid-cols-1 + md/lg/xl breakpoints) and gap scale (sm/md/lg). Primary pages (Today/Projects/My Items/Settings/ProjectDashboard) use it (e.g. "sections" + gap="lg", "metrics"). Primary header uses flex-col + sm:flex-row for action wrapping. AppShell + primitives use min-w-0 + overflow-x-hidden chains; main is independent scroller.

- Landmarks: <aside aria-label="Primary navigation"> added; existing <nav aria-label="Primary/Support/Project sections">, <main id="main">, header, footer, skip link to #main all preserved and coherent. No noisy extra landmarks.

- Dark mode via existing .dark class (providers) + CSS var overrides for surface/border/text/accent/shadow. No Tailwind dark: variants introduced.

- Scope: shell + primary command centers (Today/Projects/My Items) + shared primitives. Project subpages receive incidental consistency via shared card/grid patterns where reused.

## Rationale

Implements P08 objective and acceptance criteria: consistent scannable hierarchy and density, dark-mode card contrast/elevation via vars, visible focus/hover, semantic sequential headings (single h1 + logical h3s under dashboards), coherent landmarks/labels, no horizontal overflow, graceful 1-col collapse on tablet/narrow (desktop ~1440 / tablet ~768 / narrow ~390). Preserves skip link, advisory posture, and prior a11y (aria-current, roles).

Follows copy/layout primitives from prior phases (P07 Data Health, P01-P06 shell/dashboard work) without brand or dep changes.

## Guardrails

- No redesign of brand, colors, fonts, or tokens (vars and existing .card/.nav-item rules extended only).

- No new component library or npm dependencies.

- No changes to backend, data, auth/role simulation, or P07 copy remediation surfaces.

- Do not rewrite secondary project sub-pages into full dashboards (incidental reuse of primitives only).

- Preserve existing skip link behavior, aria-current on nav, and advisory text posture.

- Validation required: full frontend lint/typecheck/build/test + manual matrix (desktop/tablet/narrow, keyboard-only, 125% zoom) before commit.

- Post-change architecture record (this doc) + traditional commit with package manifest title/version; only the commit summary+description as final output.
