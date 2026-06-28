# Project Schedule Hub Change-Impact Fix Closeout

## Scope

Fixed Project Schedule Hub remaining-work comparison so PM-facing change-impact summaries use direct current/prior activity facts with a resolved comparison finish basis.

## Key implementation points

- Added comparison finish/start field resolution.
- Comparison finish priority: remaining_finish → finish_date → remaining_early_finish.
- Display forecast finish remains separate from comparison finish.
- Added direct current/prior remaining activity comparison by activity_id.
- Change-impact summary now comes from direct comparison.
- Diff details remain limited to upstream sequence cues.
- CPM criticality remains separate and unchanged.

## Expected TWNU18 → TWNU19 live values

- Remaining later: 461
- Remaining earlier: 76
- Finish changed: 537
- New remaining: 98
- Worsened float: 378
- Improved float: 122
- Moved remaining milestones: 6
- Comparison basis: resolved_finish_date

## Manual validation

- [x] Live API returns HTTP 200.
- [x] Current schedule is TWNU19.
- [x] Previous update is TWNU18.
- [x] Change-impact values match persisted DB comparison.
- [x] Story no longer says zero remaining activities moved later.
- [x] What Changed cards show non-zero movement.
- [x] CPM criticality still renders separately.
- [x] GMA does not appear.
- [x] Technical evidence remains collapsed by default.

## Evidence

See:
- api/project-schedule-hub-tropical.json
- api/project-schedule-hub-tropical.pretty.json
