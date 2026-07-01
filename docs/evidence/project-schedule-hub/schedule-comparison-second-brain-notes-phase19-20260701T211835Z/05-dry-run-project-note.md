---
type: schedule_comparison
note_type: schedule_update
project_key: tropical
project_label: Tropical Wind
schedule_data_date: 2026-07-01
comparison_basis: prior_update
analytics_trust_status: unavailable
identity_trust_status: unavailable
cpm_trust_status: unavailable
quality_trust_status: unavailable
generated_by: hb-personal-assistant
generation_mode: deterministic
---

# Schedule Comparison — Tropical Wind — 2026-07-01 — Compared against prior update

<!-- hb-schedule-note:begin managed -->
## Summary

- Project: Tropical Wind
- Schedule data date: 2026-07-01
- Comparison: Compared against prior update
- As of: 2026-07-03

## Trust Posture

- Analytics trust: unavailable
- Identity trust: unavailable
- CPM trust: unavailable
- Quality trust: unavailable

## Comparison Basis

Compared against prior update

## Schedule Quality Controls

Quality controls snapshot unavailable.

## Review Status

Schedule review queue has no open operator actions.

## Recommended Follow-Up

- No open review items require immediate operator action.

## Links

- controls: /projects/tropical/schedule/controls?comparison_basis=prior_update
- schedule_hub: /projects/tropical/schedule
- workbench: /projects/tropical/schedule/workbench?comparison_basis=prior_update

## Capability Limitations

- Sequence cues are advisory and highlight sequence movement for PM review only.
- HTML-in-ZIP schedule imports remain unsupported.
- Portfolio rollup uses thin per-project trust slices; large catalogs may need batching.

## Deterministic Export

# Schedule Review Memo — Tropical Wind

As of 2026-07-03

## Analytics Trust

- Status: degraded
- Identity: trusted
- Identity gate: ready
- CPM: degraded

Schedule analytics depend on trusted schedule identity for this project.

- Trust notes:
  - Out-of-sequence progress analysis is not implemented in this release; do not treat schedule movement as entitlement or causation.
  - Computed CPM is not yet available for this schedule version.
  - Schedule quality evaluation is still running.
- Capability limitations:
  - Out-of-sequence progress analysis is not implemented in this release; do not treat schedule movement as entitlement or causation.

## Schedule Review Status

- Persisted review items: 0
- Preview cues: 9
- Needs review: 0
- Accepted for PM follow-up: 0
- Dismissed as not material: 0
- Resolved: 0
- Blocked by trust/identity: 0

- Note: Identity or analytics trust is degraded/blocked; complete trust review before relying on review dispositions.

### Recommended Review Actions

- Review preview cues and persisted items, then record operator dispositions.

## Headline
Forecast finish moved 7 days later since the previous update.

## Synopsis
The current update is imp-current with data date 2026-07-01. Previous data date is 2026-06-01. 4 remaining activities moved later, 4 changed finish, and 0 lost float. Candidate driver Driver Activity in WBS-A appears connected to 3 downstream activities — review this sequence first. Review forecast finish movement

## What Changed
4 remaining activities moved later, 4 changed finish, and 0 lost float.

## Why It Matters
Candidate driver Driver Activity in WBS-A appears connected to 3 downstream activities — review this sequence first.

## Primary Driver (sequence cue)
The largest movement appears concentrated around WBS-A. Driver Activity moved by 10 days and appears connected to 3 downstream activities, including Substantial completion. Review this sequence first.

## Command Summary
- Forecast finish: 2026-08-12 (7 days vs prior)
- Remaining activities: 4
- Critical / near-critical: 0 / 0
- Negative float (remaining): 0

## Milestone Impacts

- Substantial completion: +7 days

## Float / CPM Pressure
- Negative float remaining: 0
- Near-critical remaining: 0
- Computed CPM critical remaining: 0

## Review Workbench

- [needs_review] P69 Review driver: Driver Activity (new)
- [needs_review] P67 Milestone moved later: Substantial completion (new)
- [needs_review] P65 Compression readiness: selected baseline recompute required (new)
- [needs_review] P56 Review driver: Successor B (new)
- [needs_review] P43 Review driver: Successor C (new)
- [needs_review] P19 Review driver: Substantial completion (new)
- [needs_review] P10 Metric not ready: delay analysis (new)
- [needs_review] P10 Metric not ready: window finish accuracy (new)
- [needs_review] P10 Metric not ready: window start accuracy (new)

## Top Candidate Driver
- Activity: Driver Activity
- WBS: WBS-A
- Downstream moved later: 3

## Suggested Review Agenda

1. Review driver: Driver Activity [needs_review]
2. Milestone moved later: Substantial completion [needs_review]
3. Compression readiness: selected baseline recompute required [needs_review]
4. Review driver: Successor B [needs_review]
5. Review driver: Successor C [needs_review]
6. Review driver: Substantial completion [needs_review]
7. Metric not ready: delay analysis [needs_review]
8. Metric not ready: window finish accuracy [needs_review]
9. Metric not ready: window start accuracy [needs_review]

## Caveats
- Computed CPM is unavailable for this update.
- This summary identifies schedule movement and review priorities. It does not determine delay causation, responsibility, entitlement, or compensability.
- Driver rankings and downstream chains are sequence cues for review, not causation findings.


## Source Basis

- forecast_finish: `command_summary.forecast_finish`
- forecast_finish_delta_days: `command_summary.forecast_finish_delta_days`
- negative_float_remaining_count: `command_summary.negative_float_remaining_count`
- primary_driver_narrative: `change_driver_analysis.prior_update`
- remaining_activity_count: `command_summary.remaining_activity_count`
- remaining_finish_moved_later_count: `change_impact.direct_remaining_changes.summary.finish_moved_later_count`
- review_workbench_counts: `review_workbench.summary`
- worsened_float_count: `change_impact.direct_remaining_changes.summary.worsened_float_count`
_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._
<!-- hb-schedule-note:end managed -->
