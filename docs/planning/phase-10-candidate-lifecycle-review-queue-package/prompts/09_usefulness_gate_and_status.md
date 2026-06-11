# Prompt 09 — Usefulness Gate and Status

## Objective

Extend the usefulness gate so lifecycle contradictions cannot report success.

## New contradictions

Add checks for:

- candidates exist but lifecycle/review read model is empty
- accepted actions exist but source refs are missing
- rejected items appear as new
- suppressed items appear as new
- merged source items appear as independent new items
- snoozed items appear before return date
- duplicate candidates inflate daily-brief action counts
- lifecycle stage fails but daily brief claims success
- project-review-required items hidden without explanation
- source-ref coverage below 100% for surfaced executive/actionable candidates
- lifecycle event schema/table missing when code expects it

## Status behavior

- If lifecycle checks fail in apply mode, downgrade/fail according to existing `usefulness_gate` conventions.
- Preserve last-successful pointer when the run is not useful.
- Emit a clear data-gap/status card when lifecycle data is unavailable.

## Tests

Create `tests/test_phase_10_candidate_lifecycle_usefulness_gate.py`.

Assertions:

- every contradiction above produces expected failed reason
- backward-compatible when lifecycle tables are empty but no lifecycle feature is invoked
- daily-run stage context includes lifecycle status summary

