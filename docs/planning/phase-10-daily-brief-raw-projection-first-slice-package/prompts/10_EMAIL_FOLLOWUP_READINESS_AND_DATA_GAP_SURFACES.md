# 10 — Email/Follow-Up Readiness and Data-Gap Surfaces

## Objective

Use the new raw email/thread availability honestly without overbuilding a full follow-up extraction agent in this slice.

## Required behavior

- Compute email/follow-up readiness counts:
  - raw email message rows
  - raw thread rows
  - structured email message rows
  - structured thread rows
  - model-ready thread count if available
  - existing follow-up enrichments
  - task candidates
  - commitment candidates
  - follow-up watch items
- If raw/structured email exists but follow-up layers are empty, daily brief/status must show a data-gap card such as: `email raw content available but follow-up projection not yet populated`.
- Do not claim there are no follow-ups simply because the follow-up tables are empty.

## Optional narrow improvement

If the repo already has a safe V45/V49 follow-up enrichment stage that can be invoked with caps, source refs, no raw persistence, and no cloud fallback, it may be wired as a dry-run/readiness surface. Do not expand this into a new broad NLP agent in this slice.

## Tests

- Raw email rows + empty follow-up tables => data gap, not clean empty.
- No raw email rows + empty follow-up tables => no-source or not-configured status.
- No raw content emitted.

## Acceptance

- Email/follow-up status is honest and actionable.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
