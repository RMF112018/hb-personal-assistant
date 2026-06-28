# Persisted Values Summary — TWNU18 vs TWNU19

## Purpose

This package captures persisted SQLite values for TWNU18 and TWNU19 to validate whether the Project Schedule Hub's change-impact summary is supported by stored data.

## Key files

- db/activity-columns.txt
- db/imports-twnu18-twnu19.txt
- db/persisted-row-counts.txt
- db/focused-persisted-values-twnu18-twnu19.txt
- db/sample-remaining-moved-later.csv
- db/sample-remaining-worsened-float.csv
- api/project-schedule-hub-key-sections.json
- api/health-data.json
- api/cpm-summary.json
- api/cpm-longest-path.json
- api/cpm-diagnostics.json

## Interpretation checklist

- [ ] TWNU19 is current.
- [ ] TWNU18 is prior.
- [ ] Persisted activity counts match app display.
- [ ] Persisted relationship counts match app display.
- [ ] Remaining work count matches app display.
- [ ] Negative source float count matches app display.
- [ ] CPM summary is available.
- [ ] Direct persisted activity comparison shows remaining-work movement.
- [ ] Hub change_impact agrees with direct persisted comparison.
- [ ] If hub change_impact is zero while persisted comparison is nonzero, patch hub change-impact fallback.
