You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-email-followup-candidate-projection-package/`

Before doing anything else:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main` or if unexplained dirty files are present.

Hard safety constraints:

- Do not mutate the production DB.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Use `/tmp` DB copies for apply validation.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.

# 01 — Schema and Read-Model Audit

## Objective

Confirm the structured email/thread substrate and safe read models expose enough metadata for deterministic follow-up extraction.

## Required Audit Targets

Inspect:

- V49 migrations/schema definitions for:
  - `email_message_raw_content`
  - `email_thread_raw_context`
  - `email_raw_message_structured`
  - `email_raw_thread_structured`
  - `email_raw_thread_messages_structured`
  - `email_raw_message_recipients_structured`
  - `email_raw_message_attachments_structured`
  - `raw_content_access_events`
- Read model selectors and dataclasses:
  - `select_email_message_context`
  - `select_thread_context`
  - `EmailMessageContext`
  - `ThreadContext`
  - `load_body(...)`
- Store repository methods:
  - raw email/thread getters
  - structured email/thread getters
  - recipient/attachment/message child list methods
  - raw content access audit writer

## Key Questions

Answer:

1. Which structured fields are safe to use without raw body access?
2. Which fields are missing for deterministic extraction?
3. Can the extractor identify sender/recipient direction without full recipient arrays?
4. Can stale-thread / response-needed rules be built from timestamps, sender domains, thread refs, message counts, and project keys?
5. Can commitments/tasks be extracted deterministically from structured metadata alone?
6. Where, if anywhere, is audited `load_body(...)` necessary?
7. Can raw body access be avoided for the first implementation pass?

## Required Output

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/01-schema-and-read-model-audit.md`

Include:

- table/column inventory
- safe fields to use
- unsafe fields to avoid
- body-ref/load-body policy
- schema-change decision
- exact implementation target modules

Do not print raw bodies, raw HTML, raw subjects beyond bounded/redacted labels, private URLs, or recipient arrays.
