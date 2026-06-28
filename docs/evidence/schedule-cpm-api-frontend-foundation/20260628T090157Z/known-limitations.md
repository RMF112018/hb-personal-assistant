# Known limitations (by design, Phase 8)

- **No new CPM computation** — surfaces existing Phase 1–7 results only.
- **No automatic recomputation** — read endpoints/frontend never run graph/forward/backward/float/longest-path/criticality; no writes to CPM tables (proven by a read-only test).
- **No source-field reinterpretation** — computed views use an explicit app-owned whitelist; source critical/driving-path/float/is_critical/imported early-late are never surfaced as computed CPM.
- **Source-export/proxy evidence stays separate** — shown on the existing Schedule Health page (unchanged), not duplicated or relabelled here.
- **No PM-facing storytelling/narrative/root-cause** — surfacing only; the narrative layer is Phase 9.
- **No DCMA certification claim** — only the implemented computed-CPM metric evidence.
- **No schedule diff narrative yet.**
- **Calendar limitations inherited** from prior CPM phases (working-day-equivalent offsets; no calendar engine).
- **No schema migration**; table_count unchanged (477).
- Root CLAUDE.md "no frontend/web service" line is stale (a React frontend exists) but left unchanged (out of scope).

## Pre-existing (NOT introduced by this phase)
- `npm run lint` has pre-existing errors in untouched files (e.g. ScheduleImportsPage.tsx set-state-in-effect); my changed files lint clean.
- `npm run test` has 3 pre-existing failures in MyItemsPage/TodayPage (verified failing on the clean base with my changes stashed); unrelated to schedules/CPM.

## Next recommended phase
Phase 9 — PM-Facing Schedule Storytelling Foundation (translate computed CPM + diff + DCMA/provenance into PM-facing "what changed / why it matters / downstream impact").
