# Phase 7 Findings

- Added PM-facing Schedule Controls UI to the existing Project Schedule Hub surface.
- Trend payloads are fetched from Phase 6 read-only APIs after the schedule summary resolves. The request uses the summary as-of date and falls back only to the current schedule data date.
- Frontend chart transforms are presentational: data arrays are shaped for Recharts, labels are formatted, and backend-provided point fields are displayed. Canonical counts and formulas are not recomputed in React.
- No frontend cost-weighted progress/SPI selector was added.
- No frontend formula definitions, baseline override workflow, UDF normalization, import pipeline change, or new backend route was added in Phase 7. Existing backend files in git status are prerequisite Phase 5/6 local work.
- Source/export float and computed CPM are displayed as separate provenance labels/series where provided by backend payloads.
- Driver/delay/recovery language remains review-cue oriented and avoids causation, entitlement, responsibility, and compensability determinations.
