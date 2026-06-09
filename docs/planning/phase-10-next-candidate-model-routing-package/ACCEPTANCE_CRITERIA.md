# Acceptance Criteria

The implementation is complete only when all criteria below are true.

## Repo/branch

- Work occurs on an approved experiment branch, not `main`.
- Dirty tree is clean at final handoff.
- Prompt-specific commits are present and scoped.
- Existing daily-run pilot work is not overwritten.

## Model evaluation

- Local model eval harness exists.
- Synthetic/redacted fixtures are committed.
- Optional raw local fixtures are supported only outside repo and only by explicit opt-in.
- Raw repo-contained fixture paths are refused.
- Eval output reports JSON-valid, schema-valid, redaction-pass, latency, usefulness, and error metrics.
- No raw prompt or raw model response is persisted or committed.

## Router

- Model profile config exists.
- Router selects profiles by task family.
- Router validates local availability.
- Missing/unavailable models produce blockers.
- Fallback chain is deterministic.
- No cloud fallback exists.

## Daily-brief intelligence

- Optional local model enrichment exists for daily brief quality.
- Deterministic daily-run/daily-brief behavior remains available without local model.
- Every generated bullet is source-linked or rejected.
- Generic/filler output is rejected or scored down.
- Invalid JSON/schema output is withheld.
- Redaction failure is withheld.
- Raw local consumption stays inside approved private outputs only.

## CLI

- Operator can list profiles.
- Operator can route a task family.
- Operator can run eval.
- Operator can run brief intelligence dry-run.
- JSON output is stable and raw-safe.
- Exit codes are documented and tested.

## Safety

- No email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No cloud LLM use.
- No MCP raw exposure.
- No raw private content committed.
- Guard columns remain zero where rows are written.

## Validation

- Targeted unit and CLI tests pass.
- Existing daily-run/pipeline tests pass or pre-existing failures are documented.
- Live DB-copy workflow proof exists.
- Idempotency is proven where apply/write occurs.
- Fallback is proven by simulating missing/unavailable model.
- Evidence is redacted and command-output focused.

## Documentation

- Architecture doc exists.
- Evidence README exists.
- Operator runbook exists.
- Known limitations are explicit.
- Next candidate recommendation is included.
