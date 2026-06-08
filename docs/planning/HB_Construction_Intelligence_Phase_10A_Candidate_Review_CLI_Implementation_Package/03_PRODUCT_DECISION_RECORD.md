# 03 Product Decision Record

## Decision

Build a candidate review CLI before further batch scaling or UI integration.

## Rationale

The extraction system is now technically viable. The remaining risk is semantic quality. Candidate review provides a controlled quality gate where the user can correct classifications, suppress weak candidates, accept useful ones, and build reliable downstream state.

## Product semantics

- `pending`: extracted and awaiting human review.
- `accepted`: human has accepted the candidate as a valid local record.
- `rejected`: human determined the extraction is incorrect.
- `suppressed`: human ignored it as not actionable, duplicate in meaning, low-value, or not worth surfacing.
- `snoozed`: human deferred review until a specified time.

## Important distinction

Accepted does not mean the app may send email, mutate calendar, update Graph, update Procore, or otherwise act externally. Accepted means the local record is operator-approved for future local surfaces or later gated workflows.

## Status alias decision

User-facing command `ignore` maps to stored status `suppressed`. Support `--status ignored` as a filter alias for `suppressed`, but do not introduce a new stored enum unless deliberately changing schema and validators.
