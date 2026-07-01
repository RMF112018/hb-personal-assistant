
===== EXPORT format=markdown basis=prior_update =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:09 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.md"
content-length: 4173
content-type: text/markdown; charset=utf-8

# Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility

As of 2026-07-03

## Headline
Forecast finish is unchanged, but remaining work moved materially.

## Synopsis
The current update is TWNU19 with data date 2026-06-23. Previous data date is 2026-05-26. 461 remaining activities moved later, 537 changed finish, and 378 lost float. Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first. Review remaining negative-float work

## What Changed
461 remaining activities moved later, 537 changed finish, and 378 lost float.

## Why It Matters
Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first.

## Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.

## Command Summary
- Forecast finish: 2026-11-03 (0 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711

## Milestone Impacts

- ELEVATORS FOR CONSTRUCTION USE: +1 days
- PERM POWER: +22 days
- TCO-1- AMENITIES TURNOVER: +2 days
- TCO-1- SITE DEVELOPMENT COMPLETE: +2 days
- PHASE 2 INTERIOR COMPLETION: +6 days
- ENVELOPE COMPLETION: +26 days

## Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613

## Review Workbench

- [watching] P100 Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES (existing)
  - Notes: Phase 9 validation note: confirmed review cue detail and event-history behavior on validation DB copy.
- [open] P100 Review driver: FAB/DEL WINDOW TREATMENT (existing)
- [open] P100 Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS (existing)
- [open] P86 Milestone moved later: ENVELOPE COMPLETION (existing)
- [open] P82 Milestone moved later: PERM POWER (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: PRIME PAINT DRYWALL (existing)
- [open] P68 Critical remaining: 1ST FLOOR VERTICAL (existing)
- [open] P68 Critical remaining: 2ND FLOOR  SLAB (existing)

## Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 15

## Suggested Review Agenda

1. Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES [watching]
2. Review driver: FAB/DEL WINDOW TREATMENT [open]
3. Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS [open]
4. Milestone moved later: ENVELOPE COMPLETION [open]
5. Milestone moved later: PERM POWER [open]
6. Negative float: FINISH DRYWALL [open]
7. Negative float: FINISH DRYWALL [open]
8. Negative float: FINISH DRYWALL [open]
9. Negative float: FINISH DRYWALL [open]
10. Negative float: PRIME PAINT DRYWALL [open]
11. Critical remaining: 1ST FLOOR VERTICAL [open]

===== EXPORT format=markdown basis=current_contract_baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:11 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.md"
content-length: 2971
content-type: text/markdown; charset=utf-8

# Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility

As of 2026-07-03

## Comparison Context

- Comparison Basis: Compared against Current Contract Baseline
- Source Model: named_slot
- Slot: Current Contract Baseline (current_contract_baseline)
- Current Schedule Version: tropical|1071|2026-06-23 08:00
- Comparison Schedule Version: tropical|815|2025-08-07 08:00
- Baseline Schedule Version: tropical|815|2025-08-07 08:00
- Current Data Date: 2026-06-23
- Comparison Data Date: 2025-08-07

## Headline
Remaining schedule movement compared against compared against current contract baseline.

## Synopsis
Current update TWNU19 is compared against named anchor version tropical|815|2025-08-07 08:00. 440 remaining activities moved later, 0 moved earlier, and 436 lost float.

## What Changed
Current update TWNU19 is compared against named anchor version tropical|815|2025-08-07 08:00. 440 remaining activities moved later, 0 moved earlier, and 436 lost float.

## Why It Matters
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 317 days and appears connected to 14 downstream activities, including TCO-2- SUBSTANTIAL COMPLETION / TCO. Review this sequence first.

## Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 317 days and appears connected to 14 downstream activities, including TCO-2- SUBSTANTIAL COMPLETION / TCO. Review this sequence first.

## Command Summary
- Forecast finish: 2026-11-03 (74 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711

## Milestone Impacts

- ELEVATORS FOR CONSTRUCTION USE: +74 days
- PERM POWER: +108 days
- TCO-1- AMENITIES TURNOVER: +70 days
- SITE WATER AVAILABLE: +315 days
- TCO-1- TURNOVER 99 UNITS: +28 days
- TCO-1- SUBSTANTIAL COMPLETION / TCO: +28 days
- TCO-1- AMENITIES TURNOVER: +49 days
- TCO-1- TURNOVER 99 UNITS: +18 days

## Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613

## Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 14

## Caveats
- Named-baseline export uses the selected slot schedule version as the comparison anchor.


## Source Basis

- forecast_finish: `command_summary.forecast_finish`
- forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`
- negative_float_remaining_count: `command_summary.negative_float_remaining_count`
- remaining_activity_count: `command_summary.remaining_activity_count`
- remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`
- worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`
_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._
===== EXPORT format=markdown basis=previous_progress_update_baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:13 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.md"
content-length: 2892
content-type: text/markdown; charset=utf-8

# Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility

As of 2026-07-03

## Comparison Context

- Comparison Basis: Compared against Previous Progress Update Baseline
- Source Model: named_slot
- Slot: Previous Progress Update Baseline (previous_progress_update_baseline)
- Current Schedule Version: tropical|1071|2026-06-23 08:00
- Comparison Schedule Version: tropical|1069|2026-05-26 08:00
- Baseline Schedule Version: tropical|1069|2026-05-26 08:00
- Current Data Date: 2026-06-23
- Comparison Data Date: 2026-05-26

## Headline
Remaining schedule movement compared against compared against previous progress update baseline.

## Synopsis
Current update TWNU19 is compared against named anchor version tropical|1069|2026-05-26 08:00. 461 remaining activities moved later, 76 moved earlier, and 378 lost float.

## What Changed
Current update TWNU19 is compared against named anchor version tropical|1069|2026-05-26 08:00. 461 remaining activities moved later, 76 moved earlier, and 378 lost float.

## Why It Matters
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.

## Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.

## Command Summary
- Forecast finish: 2026-11-03 (0 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711

## Milestone Impacts

- ELEVATORS FOR CONSTRUCTION USE: +1 days
- PERM POWER: +22 days
- TCO-1- AMENITIES TURNOVER: +2 days
- TCO-1- SITE DEVELOPMENT COMPLETE: +2 days
- PHASE 2 INTERIOR COMPLETION: +6 days
- ENVELOPE COMPLETION: +26 days

## Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613

## Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 15

## Caveats
- Named-baseline export uses the selected slot schedule version as the comparison anchor.


## Source Basis

- forecast_finish: `command_summary.forecast_finish`
- forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`
- negative_float_remaining_count: `command_summary.negative_float_remaining_count`
- remaining_activity_count: `command_summary.remaining_activity_count`
- remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`
- worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`
_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._
===== EXPORT format=markdown basis=secondary_progress_update_baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:14 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.md"
content-length: 3138
content-type: text/markdown; charset=utf-8

# Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility

As of 2026-07-03

## Comparison Context

- Comparison Basis: Compared against Secondary Progress Update Baseline
- Source Model: named_slot
- Slot: Secondary Progress Update Baseline (secondary_progress_update_baseline)
- Current Schedule Version: tropical|1071|2026-06-23 08:00
- Comparison Schedule Version: tropical|851|2025-11-28 08:00
- Baseline Schedule Version: tropical|851|2025-11-28 08:00
- Current Data Date: 2026-06-23
- Comparison Data Date: 2025-11-28

## Headline
Remaining schedule movement compared against compared against secondary progress update baseline.

## Synopsis
Current update TWNU19 is compared against named anchor version tropical|851|2025-11-28 08:00. 593 remaining activities moved later, 19 moved earlier, and 578 lost float.

## What Changed
Current update TWNU19 is compared against named anchor version tropical|851|2025-11-28 08:00. 593 remaining activities moved later, 19 moved earlier, and 578 lost float.

## Why It Matters
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 182 days and appears connected to 16 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.

## Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 182 days and appears connected to 16 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.

## Command Summary
- Forecast finish: 2026-11-03 (15 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711

## Milestone Impacts

- ELEVATORS FOR CONSTRUCTION USE: +103 days
- PERM POWER: +136 days
- PHASE 1 INTERIOR COMPLETION: +21 days
- TCO-1- AMENITIES TURNOVER: +10 days
- TCO-1- SITE DEVELOPMENT COMPLETE: +10 days
- SITE WATER AVAILABLE: +88 days
- SITE COMPLETION: +10 days
- PHASE 2 INTERIOR COMPLETION: +33 days
- ENVELOPE COMPLETION: +61 days
- PHASE 3 INTERIOR COMPLETION: +86 days
- UNITS 100 - 120 AVAILABLE (PHASE 2): +28 days
- UNITS 121 - 141 AVAILABLE (PHASE 2): +28 days

## Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613

## Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 16

## Caveats
- Named-baseline export uses the selected slot schedule version as the comparison anchor.


## Source Basis

- forecast_finish: `command_summary.forecast_finish`
- forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`
- negative_float_remaining_count: `command_summary.negative_float_remaining_count`
- remaining_activity_count: `command_summary.remaining_activity_count`
- remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`
- worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`

===== EXPORT format=markdown basis=baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:16 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.md"
content-length: 4173
content-type: text/markdown; charset=utf-8

# Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility

As of 2026-07-03

## Headline
Forecast finish is unchanged, but remaining work moved materially.

## Synopsis
The current update is TWNU19 with data date 2026-06-23. Previous data date is 2026-05-26. 461 remaining activities moved later, 537 changed finish, and 378 lost float. Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first. Review remaining negative-float work

## What Changed
461 remaining activities moved later, 537 changed finish, and 378 lost float.

## Why It Matters
Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first.

## Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.

## Command Summary
- Forecast finish: 2026-11-03 (0 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711

## Milestone Impacts

- ELEVATORS FOR CONSTRUCTION USE: +1 days
- PERM POWER: +22 days
- TCO-1- AMENITIES TURNOVER: +2 days
- TCO-1- SITE DEVELOPMENT COMPLETE: +2 days
- PHASE 2 INTERIOR COMPLETION: +6 days
- ENVELOPE COMPLETION: +26 days

## Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613

## Review Workbench

- [watching] P100 Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES (existing)
  - Notes: Phase 9 validation note: confirmed review cue detail and event-history behavior on validation DB copy.
- [open] P100 Review driver: FAB/DEL WINDOW TREATMENT (existing)
- [open] P100 Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS (existing)
- [open] P86 Milestone moved later: ENVELOPE COMPLETION (existing)
- [open] P82 Milestone moved later: PERM POWER (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: FINISH DRYWALL (existing)
- [open] P78 Negative float: PRIME PAINT DRYWALL (existing)
- [open] P68 Critical remaining: 1ST FLOOR VERTICAL (existing)
- [open] P68 Critical remaining: 2ND FLOOR  SLAB (existing)

## Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 15

## Suggested Review Agenda

1. Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES [watching]
2. Review driver: FAB/DEL WINDOW TREATMENT [open]
3. Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS [open]
4. Milestone moved later: ENVELOPE COMPLETION [open]
5. Milestone moved later: PERM POWER [open]
6. Negative float: FINISH DRYWALL [open]
7. Negative float: FINISH DRYWALL [open]
8. Negative float: FINISH DRYWALL [open]
9. Negative float: FINISH DRYWALL [open]
10. Negative float: PRIME PAINT DRYWALL [open]
11. Critical remaining: 1ST FLOOR VERTICAL [open]

===== EXPORT format=html basis=prior_update =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:18 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.html"
content-length: 4883
content-type: text/html; charset=utf-8

<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Schedule Review Memo</title><style>
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; line-height: 1.5; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f4f4f4; }
.disclaimer { margin-top: 2rem; font-size: 0.85rem; color: #555; }
@media print {
  body { margin: 0.75in; }
  h2 { page-break-after: avoid; }
  table { page-break-inside: avoid; }
}
</style></head><body><h1>Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility</h1><p>As of 2026-07-03</p><h2>Headline
Forecast finish is unchanged, but remaining work moved materially.</h2><h2>Synopsis
The current update is TWNU19 with data date 2026-06-23. Previous data date is 2026-05-26. 461 remaining activities moved later, 537 changed finish, and 378 lost float. Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first. Review remaining negative-float work</h2><h2>What Changed
461 remaining activities moved later, 537 changed finish, and 378 lost float.</h2><h2>Why It Matters
Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first.</h2><h2>Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.</h2><h2>Command Summary
- Forecast finish: 2026-11-03 (0 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711</h2><h2>Milestone Impacts</h2><ul><li>ELEVATORS FOR CONSTRUCTION USE: +1 days</li><li>PERM POWER: +22 days</li><li>TCO-1- AMENITIES TURNOVER: +2 days</li><li>TCO-1- SITE DEVELOPMENT COMPLETE: +2 days</li><li>PHASE 2 INTERIOR COMPLETION: +6 days</li><li>ENVELOPE COMPLETION: +26 days</li></ul><h2>Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613</h2><h2>Review Workbench</h2><ul><li>[watching] P100 Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES (existing)</li><li>[open] P100 Review driver: FAB/DEL WINDOW TREATMENT (existing)</li><li>[open] P100 Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS (existing)</li><li>[open] P86 Milestone moved later: ENVELOPE COMPLETION (existing)</li><li>[open] P82 Milestone moved later: PERM POWER (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: PRIME PAINT DRYWALL (existing)</li><li>[open] P68 Critical remaining: 1ST FLOOR VERTICAL (existing)</li><li>[open] P68 Critical remaining: 2ND FLOOR  SLAB (existing)</li></ul><h2>Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 15</h2><h2>Suggested Review Agenda</h2><p>1. Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES [watching]<br/>2. Review driver: FAB/DEL WINDOW TREATMENT [open]<br/>3. Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS [open]<br/>4. Milestone moved later: ENVELOPE COMPLETION [open]<br/>5. Milestone moved later: PERM POWER [open]<br/>6. Negative float: FINISH DRYWALL [open]<br/>7. Negative float: FINISH DRYWALL [open]<br/>8. Negative float: FINISH DRYWALL [open]<br/>9. Negative float: FINISH DRYWALL [open]<br/>10. Negative float: PRIME PAINT DRYWALL [open]<br/>11. Critical remaining: 1ST FLOOR VERTICAL [open]<br/>12. Critical remaining: 2ND FLOOR  SLAB [open]</p><h2>Caveats
- This summary identifies schedule movement and review priorities. It does not determine delay causation, responsibility, entitlement, or compensability.
- Driver rankings and downstream chains are sequence cues for review, not causation findings.</h2><h2>Source Basis</h2><ul><li>forecast_finish: `command_summary.forecast_finish`</li><li>forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`</li><li>negative_float_remaining_count: `command_summary.negative_float_remaining_count`</li><li>primary_driver_narrative: `change_driver_analysis.prior_update`</li><li>remaining_activity_count: `command_summary.remaining_activity_count`</li><li>remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`</li><li>review_workbench_counts: `review_workbench.summary`</li><li>worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`</li></ul></body></html>
===== EXPORT format=html basis=current_contract_baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:20 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.html"
content-length: 3718
content-type: text/html; charset=utf-8

<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Schedule Review Memo</title><style>
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; line-height: 1.5; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f4f4f4; }
.disclaimer { margin-top: 2rem; font-size: 0.85rem; color: #555; }
@media print {
  body { margin: 0.75in; }
  h2 { page-break-after: avoid; }
  table { page-break-inside: avoid; }
}
</style></head><body><h1>Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility</h1><p>As of 2026-07-03</p><h2>Comparison Context</h2><ul><li>Comparison Basis: Compared against Current Contract Baseline</li><li>Source Model: named_slot</li><li>Slot: Current Contract Baseline (current_contract_baseline)</li><li>Current Schedule Version: tropical|1071|2026-06-23 08:00</li><li>Comparison Schedule Version: tropical|815|2025-08-07 08:00</li><li>Baseline Schedule Version: tropical|815|2025-08-07 08:00</li><li>Current Data Date: 2026-06-23</li><li>Comparison Data Date: 2025-08-07</li></ul><h2>Headline
Remaining schedule movement compared against compared against current contract baseline.</h2><h2>Synopsis
Current update TWNU19 is compared against named anchor version tropical|815|2025-08-07 08:00. 440 remaining activities moved later, 0 moved earlier, and 436 lost float.</h2><h2>What Changed
Current update TWNU19 is compared against named anchor version tropical|815|2025-08-07 08:00. 440 remaining activities moved later, 0 moved earlier, and 436 lost float.</h2><h2>Why It Matters
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 317 days and appears connected to 14 downstream activities, including TCO-2- SUBSTANTIAL COMPLETION / TCO. Review this sequence first.</h2><h2>Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 317 days and appears connected to 14 downstream activities, including TCO-2- SUBSTANTIAL COMPLETION / TCO. Review this sequence first.</h2><h2>Command Summary
- Forecast finish: 2026-11-03 (74 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711</h2><h2>Milestone Impacts</h2><ul><li>ELEVATORS FOR CONSTRUCTION USE: +74 days</li><li>PERM POWER: +108 days</li><li>TCO-1- AMENITIES TURNOVER: +70 days</li><li>SITE WATER AVAILABLE: +315 days</li><li>TCO-1- TURNOVER 99 UNITS: +28 days</li><li>TCO-1- SUBSTANTIAL COMPLETION / TCO: +28 days</li><li>TCO-1- AMENITIES TURNOVER: +49 days</li><li>TCO-1- TURNOVER 99 UNITS: +18 days</li></ul><h2>Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613</h2><h2>Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 14</h2><h2>Caveats
- Named-baseline export uses the selected slot schedule version as the comparison anchor.</h2><h2>Source Basis</h2><ul><li>forecast_finish: `command_summary.forecast_finish`</li><li>forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`</li><li>negative_float_remaining_count: `command_summary.negative_float_remaining_count`</li><li>remaining_activity_count: `command_summary.remaining_activity_count`</li><li>remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`</li><li>worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`</li></ul></body></html>
===== EXPORT format=html basis=previous_progress_update_baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:22 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.html"
content-length: 3627
content-type: text/html; charset=utf-8

<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Schedule Review Memo</title><style>
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; line-height: 1.5; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f4f4f4; }
.disclaimer { margin-top: 2rem; font-size: 0.85rem; color: #555; }
@media print {
  body { margin: 0.75in; }
  h2 { page-break-after: avoid; }
  table { page-break-inside: avoid; }
}
</style></head><body><h1>Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility</h1><p>As of 2026-07-03</p><h2>Comparison Context</h2><ul><li>Comparison Basis: Compared against Previous Progress Update Baseline</li><li>Source Model: named_slot</li><li>Slot: Previous Progress Update Baseline (previous_progress_update_baseline)</li><li>Current Schedule Version: tropical|1071|2026-06-23 08:00</li><li>Comparison Schedule Version: tropical|1069|2026-05-26 08:00</li><li>Baseline Schedule Version: tropical|1069|2026-05-26 08:00</li><li>Current Data Date: 2026-06-23</li><li>Comparison Data Date: 2026-05-26</li></ul><h2>Headline
Remaining schedule movement compared against compared against previous progress update baseline.</h2><h2>Synopsis
Current update TWNU19 is compared against named anchor version tropical|1069|2026-05-26 08:00. 461 remaining activities moved later, 76 moved earlier, and 378 lost float.</h2><h2>What Changed
Current update TWNU19 is compared against named anchor version tropical|1069|2026-05-26 08:00. 461 remaining activities moved later, 76 moved earlier, and 378 lost float.</h2><h2>Why It Matters
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.</h2><h2>Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.</h2><h2>Command Summary
- Forecast finish: 2026-11-03 (0 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711</h2><h2>Milestone Impacts</h2><ul><li>ELEVATORS FOR CONSTRUCTION USE: +1 days</li><li>PERM POWER: +22 days</li><li>TCO-1- AMENITIES TURNOVER: +2 days</li><li>TCO-1- SITE DEVELOPMENT COMPLETE: +2 days</li><li>PHASE 2 INTERIOR COMPLETION: +6 days</li><li>ENVELOPE COMPLETION: +26 days</li></ul><h2>Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613</h2><h2>Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 15</h2><h2>Caveats
- Named-baseline export uses the selected slot schedule version as the comparison anchor.</h2><h2>Source Basis</h2><ul><li>forecast_finish: `command_summary.forecast_finish`</li><li>forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`</li><li>negative_float_remaining_count: `command_summary.negative_float_remaining_count`</li><li>remaining_activity_count: `command_summary.remaining_activity_count`</li><li>remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`</li><li>worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`</li></ul></body></html>
===== EXPORT format=html basis=secondary_progress_update_baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:23 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.html"
content-length: 3909
content-type: text/html; charset=utf-8

<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Schedule Review Memo</title><style>
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; line-height: 1.5; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f4f4f4; }
.disclaimer { margin-top: 2rem; font-size: 0.85rem; color: #555; }
@media print {
  body { margin: 0.75in; }
  h2 { page-break-after: avoid; }
  table { page-break-inside: avoid; }
}
</style></head><body><h1>Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility</h1><p>As of 2026-07-03</p><h2>Comparison Context</h2><ul><li>Comparison Basis: Compared against Secondary Progress Update Baseline</li><li>Source Model: named_slot</li><li>Slot: Secondary Progress Update Baseline (secondary_progress_update_baseline)</li><li>Current Schedule Version: tropical|1071|2026-06-23 08:00</li><li>Comparison Schedule Version: tropical|851|2025-11-28 08:00</li><li>Baseline Schedule Version: tropical|851|2025-11-28 08:00</li><li>Current Data Date: 2026-06-23</li><li>Comparison Data Date: 2025-11-28</li></ul><h2>Headline
Remaining schedule movement compared against compared against secondary progress update baseline.</h2><h2>Synopsis
Current update TWNU19 is compared against named anchor version tropical|851|2025-11-28 08:00. 593 remaining activities moved later, 19 moved earlier, and 578 lost float.</h2><h2>What Changed
Current update TWNU19 is compared against named anchor version tropical|851|2025-11-28 08:00. 593 remaining activities moved later, 19 moved earlier, and 578 lost float.</h2><h2>Why It Matters
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 182 days and appears connected to 16 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.</h2><h2>Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 182 days and appears connected to 16 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.</h2><h2>Command Summary
- Forecast finish: 2026-11-03 (15 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711</h2><h2>Milestone Impacts</h2><ul><li>ELEVATORS FOR CONSTRUCTION USE: +103 days</li><li>PERM POWER: +136 days</li><li>PHASE 1 INTERIOR COMPLETION: +21 days</li><li>TCO-1- AMENITIES TURNOVER: +10 days</li><li>TCO-1- SITE DEVELOPMENT COMPLETE: +10 days</li><li>SITE WATER AVAILABLE: +88 days</li><li>SITE COMPLETION: +10 days</li><li>PHASE 2 INTERIOR COMPLETION: +33 days</li><li>ENVELOPE COMPLETION: +61 days</li><li>PHASE 3 INTERIOR COMPLETION: +86 days</li><li>UNITS 100 - 120 AVAILABLE (PHASE 2): +28 days</li><li>UNITS 121 - 141 AVAILABLE (PHASE 2): +28 days</li></ul><h2>Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613</h2><h2>Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 16</h2><h2>Caveats
- Named-baseline export uses the selected slot schedule version as the comparison anchor.</h2><h2>Source Basis</h2><ul><li>forecast_finish: `command_summary.forecast_finish`</li><li>forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`</li><li>negative_float_remaining_count: `command_summary.negative_float_remaining_count`</li><li>remaining_activity_count: `command_summary.remaining_activity_count`</li><li>remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`</li><li>worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`</li></ul></body></html>
===== EXPORT format=html basis=baseline =====
HTTP/1.1 200 OK
date: Wed, 01 Jul 2026 15:40:25 GMT
server: uvicorn
content-disposition: attachment; filename="schedule-memo-tropical-2026-07-03.html"
content-length: 4883
content-type: text/html; charset=utf-8

<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Schedule Review Memo</title><style>
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; line-height: 1.5; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f4f4f4; }
.disclaimer { margin-top: 2rem; font-size: 0.85rem; color: #555; }
@media print {
  body { margin: 0.75in; }
  h2 { page-break-after: avoid; }
  table { page-break-inside: avoid; }
}
</style></head><body><h1>Schedule Review Memo — 23-435-01 - Tropical World Nursery Senior Living Facility</h1><p>As of 2026-07-03</p><h2>Headline
Forecast finish is unchanged, but remaining work moved materially.</h2><h2>Synopsis
The current update is TWNU19 with data date 2026-06-23. Previous data date is 2026-05-26. 461 remaining activities moved later, 537 changed finish, and 378 lost float. Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first. Review remaining negative-float work</h2><h2>What Changed
461 remaining activities moved later, 537 changed finish, and 378 lost float.</h2><h2>Why It Matters
Candidate driver FAB/DEL EXTERIOR LIGHT FIXTURES in — appears connected to 15 downstream activities — review this sequence first.</h2><h2>Primary Driver (sequence cue)
The largest movement appears concentrated around —. FAB/DEL EXTERIOR LIGHT FIXTURES moved by 42 days and appears connected to 15 downstream activities, including ENVELOPE COMPLETION. Review this sequence first.</h2><h2>Command Summary
- Forecast finish: 2026-11-03 (0 days vs prior)
- Remaining activities: 712
- Critical / near-critical: 613 / 0
- Negative float (remaining): 711</h2><h2>Milestone Impacts</h2><ul><li>ELEVATORS FOR CONSTRUCTION USE: +1 days</li><li>PERM POWER: +22 days</li><li>TCO-1- AMENITIES TURNOVER: +2 days</li><li>TCO-1- SITE DEVELOPMENT COMPLETE: +2 days</li><li>PHASE 2 INTERIOR COMPLETION: +6 days</li><li>ENVELOPE COMPLETION: +26 days</li></ul><h2>Float / CPM Pressure
- Negative float remaining: 711
- Near-critical remaining: 0
- Computed CPM critical remaining: 613</h2><h2>Review Workbench</h2><ul><li>[watching] P100 Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES (existing)</li><li>[open] P100 Review driver: FAB/DEL WINDOW TREATMENT (existing)</li><li>[open] P100 Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS (existing)</li><li>[open] P86 Milestone moved later: ENVELOPE COMPLETION (existing)</li><li>[open] P82 Milestone moved later: PERM POWER (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: FINISH DRYWALL (existing)</li><li>[open] P78 Negative float: PRIME PAINT DRYWALL (existing)</li><li>[open] P68 Critical remaining: 1ST FLOOR VERTICAL (existing)</li><li>[open] P68 Critical remaining: 2ND FLOOR  SLAB (existing)</li></ul><h2>Top Candidate Driver
- Activity: FAB/DEL EXTERIOR LIGHT FIXTURES
- WBS: —
- Downstream moved later: 15</h2><h2>Suggested Review Agenda</h2><p>1. Review driver: FAB/DEL EXTERIOR LIGHT FIXTURES [watching]<br/>2. Review driver: FAB/DEL WINDOW TREATMENT [open]<br/>3. Review driver: OWNER FAB/DEL IDENTIFICATION SIGNS [open]<br/>4. Milestone moved later: ENVELOPE COMPLETION [open]<br/>5. Milestone moved later: PERM POWER [open]<br/>6. Negative float: FINISH DRYWALL [open]<br/>7. Negative float: FINISH DRYWALL [open]<br/>8. Negative float: FINISH DRYWALL [open]<br/>9. Negative float: FINISH DRYWALL [open]<br/>10. Negative float: PRIME PAINT DRYWALL [open]<br/>11. Critical remaining: 1ST FLOOR VERTICAL [open]<br/>12. Critical remaining: 2ND FLOOR  SLAB [open]</p><h2>Caveats
- This summary identifies schedule movement and review priorities. It does not determine delay causation, responsibility, entitlement, or compensability.
- Driver rankings and downstream chains are sequence cues for review, not causation findings.</h2><h2>Source Basis</h2><ul><li>forecast_finish: `command_summary.forecast_finish`</li><li>forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`</li><li>negative_float_remaining_count: `command_summary.negative_float_remaining_count`</li><li>primary_driver_narrative: `change_driver_analysis.prior_update`</li><li>remaining_activity_count: `command_summary.remaining_activity_count`</li><li>remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`</li><li>review_workbench_counts: `review_workbench.summary`</li><li>worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`</li></ul></body></html>