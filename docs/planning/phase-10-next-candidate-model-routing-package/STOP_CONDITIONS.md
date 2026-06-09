# Stop Conditions

Stop immediately and report if any condition below occurs.

## Repo/branch

- Current branch is `main` and a new experiment branch cannot be created.
- Dirty tree contains unrelated in-progress work.
- The package would overwrite daily-run pilot work.
- Repo truth shows daily-run pilot is not present and not actually in progress; ask Bobby whether to resume pilot or continue with model routing.

## Safety

- Any implementation path requires cloud LLM use.
- Any implementation path requires email send, calendar mutation, Procore writeback, Graph writeback, or external writeback.
- Any implementation path requires credential/auth changes.
- Raw prompts or raw responses must be persisted for the feature to work.
- Raw private content would need to be committed to docs/evidence/tests.

## Data/DB

- Live DB mutation is required and Bobby has not approved it.
- A destructive migration appears necessary.
- Guard-column invariant cannot be maintained.
- DB copy cannot be created for workflow proof.

## Model quality

- Local model output cannot meet minimum JSON/schema reliability.
- Output cannot be source-linked.
- Redaction scanner cannot be made to pass.
- Deterministic fallback breaks.

## Validation

- Package-caused tests remain failing.
- Existing daily-run/pipeline behavior regresses.
- CLI surfaces emit raw unsafe data.
- Evidence cannot be redacted without losing proof value.
