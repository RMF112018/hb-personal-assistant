# Merge Readiness Checklist

Do not claim merge readiness unless every required item is checked.

## Repo / Branch

- [ ] Work is on a feature branch, not `main`.
- [ ] `main` and `origin/main` were fetched/verified before work.
- [ ] Dirty tree is fully explained.
- [ ] Changed files are limited to the email follow-up slice and evidence.

## Implementation

- [ ] Deterministic extractor implemented first.
- [ ] Structured V49 email/thread substrate is the primary source.
- [ ] Raw body access avoided by default or audited if used.
- [ ] Domain candidates persist idempotently.
- [ ] Daily-brief candidates persist through central writer.
- [ ] Every email-derived daily-brief candidate has a source ref.
- [ ] Project resolution reuses existing identity flow.
- [ ] Unresolved project-like items are review-required, not guessed.
- [ ] Daily brief shows real follow-up sections when candidates exist.
- [ ] Data-gap card remains when no candidates exist.
- [ ] Usefulness gate blocks/degrades false success.

## Validation

- [ ] Targeted tests pass.
- [ ] Commitment regression is fixed or explicitly quarantined with evidence.
- [ ] DB copy replay passes.
- [ ] Idempotency replay passes.
- [ ] Source-ref coverage is 100%.
- [ ] Executive source-ref coverage is 100%.
- [ ] Project-key coverage is reported.
- [ ] Guard columns remain zero.
- [ ] No-raw-leak scan is clean.
- [ ] Production DB untouched.
- [ ] External systems untouched.

## Handoff

- [ ] Final handoff completed.
- [ ] Known failures listed.
- [ ] Merge readiness statement is honest.
