# Phase 3 as_of Acceptance Proof

- Summary route accepts `as_of`, rejects malformed values with `400 invalid_as_of_date`, and route-spy coverage proves the parsed `date` reaches `ProjectScheduleSummaryService.build_summary`.
- Historical service selection is covered with TWNU fixtures: `2026-06-28` resolves `TWNU18`; latest after `2026-06-29` resolves `TWNU19`.
- `upstream_cues` regression coverage spies on `build_summary` from `build_drilldown(..., as_of=date(2026, 6, 28))`, proving it no longer drops historical context.
- Baseline GET and PUT both preserve `as_of` through the summary refresh path.
- Review, trend, and export route spies prove the same parsed `as_of` is forwarded to their service methods.
- Frontend page tests prove selected `asOf` reaches summary, baseline, trend, drilldown, and export helpers, and latest/current requests pass `undefined` so helpers omit `as_of`.
- API-helper tests prove summary/baseline emit `as_of` only for non-empty `asOf`, and trend/drilldown/review helpers use the same `asOf` option name.
- React Query keys in `ProjectSchedulePage` include `asOf || latest` for summary, baseline, and controls trend requests; drilldown/driver child query keys already include their `asOfDate` internal prop.
