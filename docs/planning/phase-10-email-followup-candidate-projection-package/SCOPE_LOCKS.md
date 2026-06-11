# Scope Locks

These locks are non-negotiable unless Bobby explicitly changes scope.

## Prohibited Mutations

- No production DB mutation during validation.
- No live email mutation.
- No sending email.
- No creating drafts.
- No replying to email.
- No forwarding email.
- No archiving, deleting, labeling, or marking email.
- No calendar mutation.
- No Graph writes.
- No Procore writes.
- No SharePoint writes.
- No OneDrive writes.
- No Obsidian writes except package/evidence files explicitly produced in repo.
- No external writeback paths.
- No cloud LLM calls with private raw content.

## Raw Content Prohibitions

Do not emit or store any of the following in stdout, logs, evidence, generated markdown, status JSON, browser output, tests, fixtures, DB candidate text, or model prompts/responses:

- raw email body text
- raw HTML
- unbounded raw subjects
- full recipient arrays
- full attendee arrays
- private URLs
- join URLs
- signed URLs
- web links from private records
- tokens
- secrets
- authorization headers
- cookies
- model prompts
- model responses
- access tokens or refresh tokens
- source payloads

## Schema Lock

Do not add or alter schema unless the repo-truth audit proves one of these:

1. Current domain tables cannot store deterministic follow-up/task/commitment candidates idempotently.
2. Current source-ref tables cannot attach refs to candidate rows.
3. Current status/readiness tables cannot represent the needed counts/reason codes.
4. A schema defect is causing a reproducible test failure that is directly in scope.

If schema changes are necessary:

- Use a migration.
- Add migration tests.
- Prove backward compatibility.
- Prove production DB is not mutated during validation.
- Document why a non-schema approach was insufficient.

## Validation Lock

All DB validation uses `/tmp` copies.

Allowed:

```bash
cp "$PROD_DB" "$COPY_DB"
sqlite3 "file:$COPY_DB?mode=ro" ...
```

Allowed on copy only:

```bash
.venv/bin/hb-assistant ... --db "$COPY_DB" --apply
```

Not allowed:

```bash
.venv/bin/hb-assistant ... --apply
# without explicit --db pointing to /tmp copy
```

## Evidence Lock

Evidence must contain only:

- table names
- column names
- row counts
- null/non-null counts
- source-quality distributions
- candidate counts
- source-ref coverage counts
- project-key coverage counts
- reason codes
- hash counts
- bounded redacted labels produced by existing safe system functions

Evidence must not include private raw content.
