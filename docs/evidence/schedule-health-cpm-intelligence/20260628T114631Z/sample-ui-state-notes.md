# Sample UI State Notes — Phase 9A.2

States exercised by `ScheduleQualityPage.test.tsx` (6 tests) and by reading the composed panels.

## Computed CPM Intelligence shell
- **Available** (`computed_cpm_health.available: true`): heading "Computed CPM Intelligence",
  an "Application-computed CPM" badge, a 6-pill run-chain row (Graph / Forward / Backward / Float /
  Longest path / Criticality, each "available" or "missing"), and a "View Computed CPM" link whose
  href contains `/schedules/cpm`. Verified by the new test
  *renders the Computed CPM Intelligence shell with a link when CPM is available*.
- **Unavailable** (`available: false`, or field absent): heading still renders, with
  "No application-computed CPM is available for this schedule version yet." and an "Open Computed
  CPM" link. The existing source-export sections still render (asserted). Verified by
  *renders an empty Computed CPM shell without breaking source-export sections*.
- **Partial** (some run kinds available): the run-chain row shows the available kinds as "available"
  and the rest as "missing" (the envelope's `run_chain` per-kind `available`).

## Provenance badges
- Source-export sections (Available Evidence, Critical Path/Float, Supplemental) show a
  "Source-export" badge; ≥1 present is asserted.
- Application-computed CPM section shows "Application-computed CPM"; DCMA/GAO show "Quality metric";
  Baseline shows "Baseline crosswalk"; What Changed shows "Identity-safe diff"; Findings shows
  "Derived"; Unavailable/Deferred shows "Deferred".

## Preserved states (existing tests, behavior unchanged)
- Full health render: all section headings + "Impact vs prior" / "Attention: 7 | Top WBS: WBS1" /
  project context "Tropical World Nursery - U18" / "Cost/schedule correlation: Deferred";
  `getScheduleHealthData(versionKey, 'twn')`.
- `/schedules/health` alias renders the same page.
- XER-only baseline reference → "Baseline reference detected" + "Requires companion file", no
  "failed".
- Old import without package metadata → "Limited health data available" +
  "Re-import using the package-aware workflow".

## Not yet rendered (Phase 9A.3)
Longest-path table, criticality/float distribution cards, DCMA-metric basis+caveat detail, and any
recharts visualization. The shell only links to the Computed CPM tab for that detail today.
