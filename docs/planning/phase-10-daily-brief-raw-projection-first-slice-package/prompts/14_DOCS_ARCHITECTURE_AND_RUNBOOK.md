# 14 — Docs, Architecture Note, and Operator Runbook

## Objective

Document the first-slice architecture, operator commands, and safety contract.

## Required docs

Create or update docs under `docs/architecture/` and/or `docs/runbooks/` as repo convention dictates.

Minimum content:

- V49 projection activation stage.
- Candidate projection sequence.
- Calendar candidate behavior and project review behavior.
- Procore ranking/suppression behavior.
- Source-ref/usefulness/contradiction gates.
- Email/follow-up data-gap behavior.
- Manual validation commands.
- Production rollout notes.
- Known limitations and next slice recommendations.

Use `templates/RUNBOOK_COMMANDS_TEMPLATE.md` to capture exact commands.

## Acceptance

- Docs match implemented behavior.
- Docs do not overstate follow-up/email intelligence as complete if only data-gap readiness was implemented.
- Docs contain no raw private values.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
