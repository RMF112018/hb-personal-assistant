# Scope Locks

These locks are binding for every prompt in this package.

## Hard prohibitions

- Do not mutate the production DB during validation.
- Do not run live external writeback.
- Do not send emails.
- Do not create Gmail/Graph/Outlook drafts.
- Do not create, update, or delete calendar events.
- Do not write to Graph.
- Do not write to Procore.
- Do not write to SharePoint, OneDrive, or Obsidian.
- Do not expose raw email bodies.
- Do not expose raw HTML.
- Do not expose full recipient arrays.
- Do not expose full attendee arrays.
- Do not expose join URLs, private URLs, signed URLs, or download URLs.
- Do not expose tokens, secrets, authorization headers, or bearer-like strings.
- Do not expose unbounded raw subject/title/body text.
- Do not store or print model prompts/responses.
- Do not run cloud LLMs over private raw content.
- Do not delete candidates as a substitute for lifecycle.
- Do not hide source-ref-missing candidates without a degraded/withheld status.
- Do not accept or promote candidates without source refs unless repo truth documents a narrow exception and the usefulness/status layer reports it.

## Schema lock

Avoid schema changes unless the repo-truth audit proves existing tables cannot represent cross-family lifecycle cleanly and idempotently.

If schema is required:

- It must be additive.
- It must follow existing SQLite migrator conventions.
- It must preserve V1-current tables.
- It must include guard columns or align to the repo's current guard-column contract.
- It must include tests and `/tmp` DB-copy validation.
- It must not backfill raw content.

## Existing behavior lock

Do not break existing:

- `candidate_review.py` task/commitment review service behavior.
- `second-brain review` CLI behavior.
- `accepted_tasks` / `accepted_commitments` promotion behavior.
- `follow_up_watch` monitor behavior.
- `source_ref_gate` fail-closed behavior.
- daily-brief candidate projection idempotency.
- guard-column zero invariant.

