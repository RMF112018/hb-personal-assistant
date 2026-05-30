# 03 — Email Schema and Migrations (Phase 06 Prompt 03)

Migration **V11** · additive · read-only / metadata-only · no destructive change

This prompt adds the operational email-intelligence **data plane** — the SQLite tables the
read-only pipeline (discovery → metadata index → project match → relationship candidates → review
routing → thread summaries) writes to — plus the store-adapter helpers (upserts, idempotency,
crawl-run + processing receipts, review-queue reads). V10 (Prompt 02) had already landed the
active policy + mailbox source registry; V11 builds the rest of the schema on top of it.

Raw captured validation: [`email-schema-validation.txt`](./email-schema-validation.txt).

## Reconciliation (package proposal ↔ repo truth)

The package SQL (`resources/sql/phase_06_email_operational_schema_proposal.sql`) declared **11**
tables, but `email_source_locations` **already exists in V10 and is byte-for-byte identical**.
V11 therefore adds only the **10 new tables** and references the existing V10
`email_source_locations(source_id)` via foreign keys — it never re-creates or alters it. The
proposal's CHECK constraints are kept **verbatim** because they encode the guardrails. No new
runtime scope, no mutation path, no full-body persistence, no attachment-content download.

| V11 table | Purpose | Guardrail CHECKs |
|---|---|---|
| `email_sync_state` | per-(source, folder) bounded-lookback sync cursor | — (PK `source_id, folder_id`) |
| `email_crawl_runs` | crawl/index run receipts | `mailbox_mutation_attempted=0`, `full_body_persisted=0`, `attachment_content_downloaded=0` |
| `email_messages` | message **metadata** (no full body) | `full_body_persisted=0`, `mailbox_mutation_allowed=0`, `extraction_policy` default `metadata_only` |
| `email_message_recipients` | To/Cc/Bcc, hashed addresses | `UNIQUE(message_id, recipient_role, address_hash)` |
| `email_message_attachments` | attachment **metadata** only | `metadata_only=1`, `content_downloaded=0` |
| `email_project_matches` | per-message project-match signals | `UNIQUE(message_id, project_key, match_signal)` |
| `email_relationship_candidates` | cross-system link candidates (Procore/SharePoint/Calendar) | `UNIQUE(message_id, candidate_type, target_table, target_key, match_signal)` |
| `email_thread_summaries` | thread-level summaries (model output, preview-bounded) | PK `thread_key` |
| `email_review_queue` | sensitivity / low-confidence routing | `UNIQUE(message_id, category, reason)` |
| `email_processing_receipts` | local-processing audit trail | `mailbox_mutation_attempted=0`, `full_body_persisted=0`, `attachment_content_downloaded=0` |

**No full email body is stored.** `email_messages` carries only a bounded, redacted
`body_preview_excerpt_redacted` + `body_preview_hash` (the package explicitly permits bounded,
redacted preview handling). A column-level assertion confirms no `body`/`content`/`text`/
`full_text`/`full_body` column exists.

## What landed

- **`src/hb_assistant/store/migrator.py`** — `V11_STATEMENTS` (10 `CREATE TABLE IF NOT EXISTS` +
  7 indexes) and the V11 apply-gate block recording
  `v11_email_operational_intelligence_schema`. V1–V10 statements untouched; the V5
  `construction_email_intelligence_deferred_state` row is preserved.
- **`src/hb_assistant/construction/store/repositories.py`** — `ConstructionStore` helpers mirroring
  the V10 idioms (`get_connection`/`transaction`/`_utc_now`/`_dump_json`/`zip(strict=True)`):
  `upsert_email_sync_state`/`get_email_sync_state`, `insert_email_crawl_run`/
  `complete_email_crawl_run`, `upsert_email_message`/`get_email_message`/`list_email_messages`,
  `add_email_message_recipient`/`list_email_message_recipients`,
  `upsert_email_message_attachment`, `upsert_email_project_match`,
  `upsert_email_relationship_candidate`, `upsert_email_thread_summary`,
  `enqueue_email_review_item`/`list_email_review_queue`/`count_email_review_queue`,
  `insert_email_processing_receipt`/`list_email_processing_receipts`. Every mutating helper raises
  `ValueError` **before SQL** on any no-mutation / no-full-body / no-attachment-content flag.
- **`tests/test_email_operational_schema_v11.py`** — 27 tests: migration mechanics (apply()==11,
  tables/indexes present, V1–V10 + deferred row preserved, idempotent, `email_source_locations`
  not re-declared), database-layer CHECK `IntegrityError`s, adapter `ValueError` guards, helper
  round-trips, recipient/review-queue idempotency, and the no-full-body column assertion.
- **Version-assert bumps** `== 10` → `== 11` in `test_construction_store_repositories.py`,
  `test_email_registry_migration_v10.py`, `test_procore_financials_v8.py`,
  `test_procore_financials_v9.py`, `test_procore_history_migration_v7.py`.

## Four-layer read-only lock (extended to the data plane)

1. **Adapter** — `ValueError` before SQL (observed: `full_body_persisted must be False`, etc.).
2. **Database** — SQLite `CHECK` → `IntegrityError` (observed: `CHECK constraint failed:
   full_body_persisted = 0`, `content_downloaded = 0`, `metadata_only = 1`, …).
3. **Scope** — runtime still requests `Mail.Read` only (unchanged from Prompt 00/02).
4. **Endpoint contract** — GET-only allowlist / mutation blocklist (Prompt 01) unchanged.

## Validation

- `tests/test_email_operational_schema_v11.py` → **27 passed**.
- Touched migration-version + repository tests → **green** (assertions bumped 10→11).
- `ruff check .` → All checks passed. `mypy src` → no issues (117 source files).
  `python -m compileall -q src tests` → OK.
- Full safe subset (`-m "not integration and not live and not manual"`) → green **except 4
  pre-existing, date-driven failures in `tests/test_automation.py`** (today, 2026-05-30, is a
  Saturday and the morning orchestrator skips weekends). These were confirmed unrelated: they
  persist with the V11 source changes stashed and reference no email/migrator code.

## Stop conditions — none triggered

No mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send` request, no destructive migration
(additive `CREATE TABLE IF NOT EXISTS` only; V1–V10 intact), no full-body default persistence, no
attachment-content default download.
