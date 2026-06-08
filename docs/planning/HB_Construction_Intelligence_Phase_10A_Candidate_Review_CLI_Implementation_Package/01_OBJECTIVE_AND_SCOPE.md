# 01 Objective and Scope

## Objective

Implement a CLI review workflow for persisted Phase 10A local-model candidates. The workflow must allow the user to inspect, correct, accept, reject, ignore/suppress, snooze, batch-triage, export, and summarize extracted candidates before any downstream automation or UI integration.

## Current business need

Phase 10A extraction is operational for capped batches and can persist task/commitment candidates safely. The next highest-value feature is not more extraction volume. It is a human review layer because extraction quality is useful but not semantically perfect.

Observed issues include:

- assignee/waiting-state misclassification;
- aggressive inference on weak signals;
- financial/schedule candidates that may be useful but must remain review-gated;
- candidate records that need local correction before they can safely feed UI or downstream automation.

## In scope

- CLI command group under `hb-assistant second-brain review`.
- Review list/show/summary.
- Accept, reject, ignore/suppress.
- Snooze.
- Edit/correct redacted candidate fields.
- Batch actions by candidate ID file.
- Export review queue in redacted JSON.
- Store-layer methods for candidate reads and state transitions.
- Reliable append-only review event audit trail.
- Small additive V43 migration if required.
- Targeted tests and guardrail proofs.

## Out of scope

- New extraction prompts or prompt tuning.
- Broader packet extraction scope.
- UI work.
- Graph, Procore, email, calendar, Slack, Teams, SMS, notification, or MCP writeback.
- External/cloud LLM dependency.
- Automatic candidate acceptance.
- Production scheduler changes.
- Raw content exposure through CLI, API, MCP, logs, evidence, or export files.
