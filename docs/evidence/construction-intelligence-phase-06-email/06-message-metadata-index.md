# 06 — Message Metadata Indexing (bounded, read-only, idempotent)

Phase 06 Prompt 06 · read-only / metadata-only · no mailbox mutation · no new scope

Bounded discovery of messages in the included folders (Inbox / Sent Items / Archive) within a lookback
window, normalized to **redacted, metadata-only** rows, persisted to `email_messages` +
`email_message_recipients` + `email_message_attachments`, with `email_crawl_runs` +
`email_processing_receipts` as the run audit trail. Mailbox is read-only (GET + body-free `$select`,
through the endpoint guard); attachments are metadata-only (no `contentBytes`); the only writes are
local SQLite. Re-running is idempotent.

## What landed

- **`src/hb_assistant/construction/email/message_indexer.py`** (new) — `EmailMessageIndexer(mail_client,
  store)` with `index(*, project_key=None, lookback_days=None, dry_run=False, max_messages_per_folder=200)`.
  Reads included folders' raw `folder_id` from the persisted `email_source_locations` (self-heals via
  folder discovery if absent), then per folder lists bounded messages
  (`received_after` `$filter` + `$top` + `max_items` cap), normalizes each (redacted), and upserts
  message + recipients + attachment metadata; records a crawl run per folder + one processing receipt.
- **`src/hb_assistant/cli/graph.py`** — `graph mail index --project … --lookback-days … --max-messages …
  [--dry-run/--no-dry-run] --json` (default persist).
- **`resources/config/graph_mail_read_endpoint_allowlist.yaml`** — removed `sensitivity` from
  `message_metadata_select` (see reconciliation below).

## Reconciliation (package ↔ repo truth)

- **`--project` is a validated crawl-run label, not a filter/match.** Repo truth
  (`docs/architecture/17-email-intelligence-phase-06.md`) orders the pipeline `… → metadata index →
  project match → …` with **project matching as a later prompt**. So `index` performs bounded metadata
  indexing of Bobby's folders and records `project_key` on the crawl run/receipt
  (`get_project_identity("tropical")` validates the label; `project_resolved` reflects whether the
  identity row is present in the local DB). It does **not** populate `email_project_matches` or set
  `project_number_detected`/`project_match_confidence` — that is the next slice.
- **`index` defaults to persist** (`--dry-run` is opt-in preview) — the canonical command must index to
  prove idempotency.
- **Live contract fix:** the Prompt 01 allowlist listed `sensitivity` in `message_metadata_select`, but
  `sensitivity` is **not a valid property** on the Graph v1.0 `message` entity — selecting it returns
  `HTTP 400 "Could not find a property named 'sensitivity' on type 'Microsoft.OutlookServices.Message'"`.
  This only surfaced on the first live `list_messages` call. Removed it from the allowlist (the other
  19 fields verified valid live). `email_messages.sensitivity_metadata` is now simply left null.

## Live validation — `hb-assistant graph mail index --project tropical --lookback-days 30 --max-messages 25 --json`

Both runs exit 0. Per-folder (run 1): archive seen/indexed 2/2, inbox 25/25, sent 25/25 — totals
**messages 52, recipients 237, attachments 73**. (`--max-messages 25` caps Inbox/Sent; Archive had 2 in
window.)

### Idempotency proof (run twice; data rows stable, audit rows accumulate)

| table | after run 1 | after run 2 |
|---|---|---|
| `email_messages` | 52 | **52** |
| `email_message_recipients` | 237 | **237** |
| `email_message_attachments` | 73 | **73** |
| `email_crawl_runs` | 6 | 9 (+3, one per folder per run — audit log) |
| `email_processing_receipts` | 2 | 3 (+1 per run — audit log) |

Message/recipient/attachment rows are upserted by stable keys (`message_id`,
`UNIQUE(message_id, recipient_role, address_hash)`, `attachment_key`), so re-running does not
duplicate. Crawl-run + receipt rows are append-only run logs and accumulate by design.

## Guardrails

- **Read-only / metadata-only:** only `get_me`, `list_messages`, `list_attachment_metadata` (guarded
  GETs with a body-free `$select`). No `body`; attachment `$select` excludes `contentBytes`.
- **Redaction:** subject stored as `[redacted:hash]` + `subject_hash`; sender/recipient addresses
  hashed (domain retained); bounded `body_preview_excerpt_redacted` (120 chars) + `body_preview_hash`.
  The `--json` output and this evidence carry **counts only** — no subjects, addresses, or raw ids.
- **Bounded:** lookback (30d, validated 1–366) + `--max-messages` cap; never a full-mailbox backfill.
- **No write scope:** runtime requests `Mail.Read` only. Leak scan of both run outputs: clean.

## Verification

- `tests/test_email_message_indexer.py` (persist counts, `is_bobby`, thread_key conversation/​hash
  fallback, idempotency, dry-run no-persist, bounded cap) + `tests/test_graph_mail_cli.py` index case →
  pass. Contract/guard/client/lockout tests → green after the allowlist change.
- `ruff check .` clean; `mypy src` no issues (121 files); `compileall` OK.
- Full safe subset green **except 4 pre-existing weekend-driven `test_automation.py` failures** (today,
  2026-05-30, is a Saturday; orchestrator skips weekends) — unrelated.

## Stop conditions — none triggered

No mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send` request, no destructive migration, no
full-body default persistence, no attachment-content download. The only writes are local SQLite.
