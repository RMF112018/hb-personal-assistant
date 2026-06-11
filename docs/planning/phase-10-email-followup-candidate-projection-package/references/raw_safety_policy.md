# Raw Safety Policy

## Default

The email follow-up projection path is structured-first and metadata-first.

## Raw Access

Raw body access is allowed only when all are true:

1. A deterministic candidate family cannot be implemented safely from structured metadata.
2. The caller uses an existing `load_body(...)` accessor.
3. `raw_content_access_events` records the access.
4. The extracted result is bounded/redacted.
5. Tests prove raw content does not leak.
6. Evidence records only counts and reason codes.

## Prohibited Outputs

Never emit:

- body text
- body HTML
- body preview text beyond existing bounded/redacted system policy
- join URLs
- signed URLs
- web links from private source records
- raw recipient arrays
- raw attendee arrays
- tokens/secrets
- headers/cookies
- model prompts/responses
- full raw subjects if unbounded

## Evidence

Evidence can include:

- row counts
- candidate counts
- source-quality distribution
- source-ref coverage
- project-key coverage
- review-required counts
- reason codes
- synthetic sentinel test names
- no-leak scan verdicts

Evidence cannot include raw private values.
