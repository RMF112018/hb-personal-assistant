# Prompt 08 — Daily Brief Lifecycle Integration

## Objective

Make the daily brief lifecycle-aware without misleading success.

## Required behavior

The daily brief should distinguish:

- new candidates requiring review
- accepted actions
- waiting-on-others items
- user commitments
- third-party commitments
- stale accepted actions
- snoozed items returning today
- rejected/suppressed items hidden from normal view
- unresolved project candidates needing review
- source-ref missing candidates withheld or degraded

The daily brief must not show:

- raw bodies
- raw HTML
- full recipient/attendee arrays
- private URLs
- join URLs
- signed URLs
- tokens/secrets
- model prompts/responses
- unbounded subject/body text

## Integration points

Audit and update as needed:

- `daily_brief_context_packet.py`
- deterministic renderer / markdown renderer
- browser/html brief output
- `source_ref_gate.py`
- email-follow-up readiness/data-gap surface
- stage context receipts

## Tests

Create `tests/test_phase_10_candidate_lifecycle_daily_brief.py`.

Assertions:

- rejected/suppressed/merged duplicates absent from normal brief
- snoozed item absent before return date and returns on due date
- accepted action appears in accepted/open section
- stale accepted action appears as stale
- project-review-required visible with explanatory status
- source-ref-missing surfaced candidates are withheld/degraded
- rendered output no-raw-leak scan passes

