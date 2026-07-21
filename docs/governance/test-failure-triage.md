# Test Failure Triage and Durable Ownership

This procedure implements the durable ownership requirements in
`.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md`.

## Immediate record

Every observed failing test receives a durable record before the discovering
work item advances beyond the affected checkpoint. The preferred record is a
GitHub issue created from `.github/ISSUE_TEMPLATE/test-failure.yml`; its stable
identity is `TF-<issue-number>`. A repository goal finding ledger may be used
when it provides the same required fields and immutable history.

The record must contain the discovery time, source work item, exact failing test
IDs, triage owner, classification state, base/candidate evidence, affected gate,
current disposition, corrective authorization state, and closure evidence.

Creating or updating the triage record is not corrective implementation
authority. The primary agent may create or request the record, but only the
operator or a validated deterministic controller may authorize a corrective
work item or parallel agent.

## Required states

A failure starts as `RELATIONSHIP_UNKNOWN` unless direct evidence supports a
more specific classification. Corrective authorization starts as
`AWAITING_AUTHORIZATION` unless the exact authorization already exists.

A record may close only after the applicable correction, independent review,
combined-candidate validation, and final gate disposition are linked. A
pre-existing failure may remain outside the primary work item's edit scope, but
it may not be unowned, untracked, or treated as green.
