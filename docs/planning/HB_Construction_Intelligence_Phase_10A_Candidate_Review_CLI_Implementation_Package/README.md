# HB Construction Intelligence Phase 10A Candidate Review CLI Implementation Package

## Purpose

This package directs the next repository update for `hb-personal-assistant`: implement a CLI workflow that lets the operator inspect and triage Phase 10A local-model candidates before any UI or downstream automation consumes them.

## What this package is

- A source-truth implementation guide for the local coding agent.
- A numbered prompt set with ordered execution steps.
- A schema decision package for a small V43 additive migration.
- A safety/validation package preserving no-raw/no-writeback semantics.
- A runbook package for manual validation against the existing populated dev DB.

## What this package is not

- It is not a request to run more extraction batches.
- It is not a UI integration package.
- It is not an external writeback or automation package.
- It is not a model-prompt retuning package.
- It does not authorize cloud LLM dependencies.

## First file to read

Start with `00_PACKAGE_MANIFEST.md`, then execute prompts in `prompts/` in numeric order.

## Minimum final commands expected after implementation

```bash
hb-assistant second-brain review summary --json
hb-assistant second-brain review list --status pending --limit 25 --json
hb-assistant second-brain review show --candidate-id <candidate_id> --json
hb-assistant second-brain review accept --candidate-id <candidate_id> --json
hb-assistant second-brain review ignore --candidate-id <candidate_id> --reason "not actionable" --json
hb-assistant second-brain review reject --candidate-id <candidate_id> --reason "incorrect extraction" --json
```

## Optional commands expected if V43 migration is implemented

```bash
hb-assistant second-brain review snooze --candidate-id <candidate_id> --until 2026-06-12T09:00:00-04:00 --json
hb-assistant second-brain review edit --candidate-id <candidate_id> --title "..." --assignee user --waiting-state waiting_on_me --json
hb-assistant second-brain review export --status pending --out /tmp/phase10a_review_queue.json --json
```

## Non-negotiable guardrails

- No raw email body, raw document text, raw calendar payload, raw Procore payload, raw prompt, raw response, signed URL, download URL, token, or secret persistence or output.
- No email send, calendar mutation, Graph writeback, Procore writeback, external writeback, or MCP raw-content exposure.
- Review actions update local candidate review state only.
- Source refs remain intact and immutable.
- Accepted means operator-approved candidate record, not approval to perform external work.
