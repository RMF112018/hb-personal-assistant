# Scope Locks

These locks are non-negotiable unless Bobby explicitly changes scope.

## Prohibited Mutations

- No production DB mutation during validation.
- No live email mutation.
- No sending email.
- No creating drafts.
- No replying to email.
- No forwarding email.
- No calendar mutation.
- No Graph writes.
- No Procore writes.
- No SharePoint writes.
- No OneDrive writes.
- No Obsidian writes except package/evidence files explicitly produced in repo.
- No lifecycle state mutation from telemetry.
- No candidate source-ref mutation from telemetry.
- No external writeback paths.
- No cloud LLM calls with private raw content.
- No scheduled integration until on-demand read-only evaluation is implemented and validated.

## Raw Content Prohibitions

Do not emit or store any of the following in stdout, logs, evidence, generated markdown, status JSON, browser output, tests, fixtures, DB telemetry tables, or model prompts/responses:

- raw email body text
- raw email HTML
- raw calendar body or attendee arrays
- raw Procore endpoint payload JSON
- raw document text
- unbounded raw subjects/titles
- private URLs
- join URLs
- signed URLs
- Graph web links from private records
- local absolute paths from Bobby's machine
- tokens
- secrets
- authorization headers
- cookies
- model prompts
- model responses
- source payloads
- raw markdown/html brief bodies

## Schema Lock

Do not add schema unless the repo-truth audit proves the ranking/assembly prerequisite exists. If absent, stop and write a blocker handoff.

If schema changes proceed:

- Add one migration version only: `LATEST_SCHEMA_VERSION + 1`.
- Use additive `CREATE TABLE IF NOT EXISTS` and indexes only unless repo truth demands guarded additive column reconciliation.
- Do not drop, rename, rewrite, or backfill destructive data.
- Add full Phase 10 guard columns to every telemetry table.
- Do not add raw-content exempt telemetry tables.
- Persist metadata, hashes, counts, reason codes, policy versions, and aggregate metrics only.

## Validation Lock

All DB apply validation uses `/tmp` copies.

Allowed:

```bash
cp "$PROD_DB" "$COPY_DB"
sqlite3 "file:$COPY_DB?mode=ro" ...
.venv/bin/hb-assistant ... --db "$COPY_DB" --apply --max-persist N
```

Not allowed:

```bash
.venv/bin/hb-assistant ... --apply
# without explicit --db pointing to /tmp copy
```

## Evidence Lock

Evidence may contain:

- table names
- column names
- row counts
- non-null/null counts
- source-ref coverage counts
- candidate family counts
- lifecycle outcome counts
- policy/model/profile ids
- hashes
- reason codes
- scanner category codes
- aggregate metrics
- bounded redacted text only when produced by existing safe repo conventions and scanner-clean

Evidence must not contain raw/private content.
