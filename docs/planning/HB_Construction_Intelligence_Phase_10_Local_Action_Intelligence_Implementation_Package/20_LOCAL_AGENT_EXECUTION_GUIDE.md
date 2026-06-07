# 20 Local Agent Execution Guide

## Working rules

- Work from current repo truth.
- Do not trust this package over code.
- Implement in small commits.
- Run targeted tests after each prompt.
- Do not skip no-raw/no-writeback proofs.
- Keep UI copy end-user friendly.

## Branch suggestion

`phase-10-local-action-intelligence`

## Execution order

Run prompts in numeric order. Do not start UI prompts until backend/API schemas and fixtures are in place.

## Commit message template

```text
Phase 10 Prompt NN: <summary>

- <what changed>
- <why it is safe>
- <tests/evidence>
- <known limitations>
```
