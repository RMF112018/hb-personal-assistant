# Frontend surfacing (Phase 8)

## Pages/components
- New tab "Computed CPM" at `/schedules/cpm` (`frontend/src/pages/ScheduleCpmPage.tsx`), nav entry in `SchedulePageChrome.tsx`, route in `app/routes.tsx`. Reuses ScheduleShell/BackLink/Subnav/PageHeader, ScheduleProjectPicker/ScheduleVersionPicker, SchedulePanel/ScheduleTable, EmptyState — and the SAME `?project=&version=` query-param selection semantics as the other schedule pages (project/version carry across tabs).
- API client: `getScheduleCpmSummary/Activities/LongestPath/Diagnostics` + types in `lib/api.ts`.

## Sections
1. CPM run-chain card — per-run status pills (graph/forward/backward/float/longest path/criticality) + missing reasons + caveat "Application-computed CPM; source-export evidence shown separately".
2. DCMA critical-path metric card — status (source-only not measurable / application-computed CPM available / attempted not measurable), basis, dependency run ids, reason codes/caveats, "source critical flags used: false".
3. Longest Path panel — labelled "Longest Path" (NOT "Critical Path"); ordered activity table (sequence, id, name, ES/EF, total float, criticality class).
4. Computed activity table — id, name, ES/EF/LS/LF, total/free float, criticality class, longest-path member.
5. Source-export separation note pointing to Schedule Health (separate, unchanged).

## Copy/labels
Approved phrases only (Application-computed CPM, Computed criticality, Longest path, Source-export evidence, "Not measurable until CPM calculation chain is available", "DCMA critical-path metric is based on application-computed CPM evidence"). Avoided: certified, true/P6 critical path, root cause, narrative, schedule story.

## Empty/error states
Select-version, loading, error ("Could not load computed CPM"), no-CPM ("No computed CPM yet"), per-panel empty (longest path / activities) — all via EmptyState.

## Rendering notes (screenshots not practical in this environment)
Verified via 7 vitest + RTL tests: empty state; run-chain statuses; DCMA computed-vs-source-export distinction; "Longest Path" present and "Critical Path" absent; ordered path + computed activity fields; missing-dependency reasons; API-failure error state.
