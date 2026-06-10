# Email + Calendar Full Raw Content Ingestion + Structured Projection Package

## Objective

Implement a repo-truth, policy-gated transition from redacted / metadata-only email and calendar storage to useful full raw local SQLite content **and final structured projections** for Bobby's private DB.

This package is designed for one-shot execution by Bobby's local code agent with:

```text
Execute the objective defined at docs/planning/email_calendar_full_raw_content_ingestion_package/README.md
```

The intent is not to weaken outbound redaction. The intent is to make the private local DB a useful system of record while keeping stdout, logs, repo evidence, browser/status JSON, Obsidian, daily brief output, model prompts, and committed fixtures redacted by default.

## Non-negotiable completion standard

Raw landing tables are not the finish line.

The local code agent may not mark this package complete until it has proven that every available raw email/calendar business field has a final structured projection destination. This mirrors the Procore endpoint-specific projection standard: capture is necessary, but capture without queryable structured projections is incomplete.

Completion requires a mechanical field inventory and projection matrix for every available raw source family:

- `email_message_raw_content`
- `email_thread_raw_context`
- `calendar_event_raw_content`
- any new raw landing table introduced during implementation
- every nested JSON field path inside recipient, attachment, thread-message, attendee, recurrence, location, and online-meeting sidecars

For each available source family, completion requires:

```text
unmapped_primary_business_fields = 0
unmapped_nested_business_fields = 0
observed_nested_arrays_without_child_table_or_mapped_sidecar = 0
projected_parent_rows_match_raw_parent_rows, except explicitly documented policy exclusions
```

Allowed destinations are:

- endpoint/source-family primary structured table column;
- child/detail table column;
- dimension table column;
- bridge table column;
- documented lossless sidecar JSON column in a final structured projection table;
- explicit non-business / transport-secret / policy-blocked exclusion with a reason.

The agent must not claim completion by pointing to `email_message_raw_content`, `email_thread_raw_context`, or `calendar_event_raw_content` alone. Those are raw/landing sources. The acceptance target is the **final structured projection layer** plus coverage proof.


## Repository

```text
Repository: RMF112018/hb-personal-assistant
Local path: /Users/bobbyfetting/hb-personal-assistant
Package path: docs/planning/email_calendar_full_raw_content_ingestion_package/
```

## Repo-truth audit verdict

The repository already contains the core V42 raw-content tables required for local plaintext email/calendar content, but the active ingestion and consumer surfaces remain inconsistent:

- Legacy/base email and calendar paths are still metadata/redacted-only.
- Phase 10A added raw email/calendar ingestion branches, but they are not yet sufficient as a decisive production-quality raw system of record or structured analytical projection layer.
- Source-quality classification and field-path projection coverage are not yet first-class acceptance gates for email/calendar raw rows.
- Legacy metadata/redacted rows can still be the dominant source for daily brief, meeting prep, relationship extraction, retrieval, and model context unless consumers are explicitly redirected through policy-aware raw read models.
- Outbound redaction posture is strong and should be retained.

## Current repo-truth findings

### Schema

Current schema head observed in `src/hb_assistant/store/migrator.py` is **V46**.

Existing raw-content tables introduced in V42:

- `raw_content_policy_state`
- `email_message_raw_content`
- `email_thread_raw_context`
- `calendar_event_raw_content`
- `raw_content_model_context_packets`
- `raw_content_access_events`

Current older tables still constrain legacy behavior:

- V10 email policy pins the original email intelligence default to metadata-only and no full-body storage.
- V11 `email_messages` stores redacted subject, preview hash/excerpt, recipients/attachments metadata, and `full_body_persisted CHECK(full_body_persisted = 0)`.
- V12 encrypted body vault references persist only a vault ref/hash/length, not plaintext in SQLite.
- V23 calendar/event index persists hashed/redacted calendar metadata only and has raw/full-text guard columns.
- V25 meeting-prep and cross-source relationship tables store redacted sections/evidence only.
- V26+ second-brain / daily-brief tables keep raw body, raw prompt/response, retrieved context, URLs, and writeback guard columns at zero.
- V45 email follow-up enrichments are structured/redacted model outputs and hashes only; they are not the full raw store.
- V46 Procore has moved toward raw local payload capture and structured raw bronze tables; email/calendar need the analogous source-quality and consumer handoff discipline.

### Email ingestion

Relevant current code paths:

- `src/hb_assistant/graph/mail_client.py`
- `src/hb_assistant/construction/email/message_indexer.py`
- `src/hb_assistant/construction/email/endpoints.py`
- `src/hb_assistant/normalize/email.py`
- `src/hb_assistant/store/repositories.py`

Current behavior:

- Older `MailClient.list_inbound()` / `list_sent()` select `bodyPreview`, not `body`.
- Older `MailClient.get_message(..., include_body=True)` only requests `body` when `cfg.mail.persist_full_body` is true, and `MailConfig.persist_full_body` defaults false.
- `get_message_body_for_inspection()` fetches body in-memory only, truncates, and intentionally avoids persistence.
- `EmailMessageIndexer` now has `include_raw_content` / raw policy logic and calls `get_message_body()` for each message when raw mode is effective, then upserts `email_message_raw_content` and `email_thread_raw_context`.
- The raw branch currently needs hardening around policy semantics, bounded run controls, source-quality, overwrite precedence, access-event logging, project/source links, and consumer handoff.
- `construction/email/endpoints.py` is read-only and can attach raw content from `email_message_raw_content` / `email_thread_raw_context`, but it performs no Graph calls and therefore cannot compensate for missing raw rows.

### Calendar ingestion

Relevant current code paths:

- `src/hb_assistant/graph/calendar_client.py`
- `src/hb_assistant/construction/calendar/event_indexer.py`
- `src/hb_assistant/construction/calendar/endpoints.py`
- `src/hb_assistant/normalize/calendar_event.py`
- `src/hb_assistant/construction/meeting_prep/brief_builder.py`

Current behavior:

- Older `CalendarClient.list_events()` selects calendar metadata only: no body, attendees, recurrence, or full online meeting payload.
- V23 calendar indexer originally documented body-/join-url-free metadata indexing.
- `CalendarEventIndexer` now has `include_raw_content` / raw policy logic and calls `get_event()` when raw mode is effective, then upserts `calendar_event_raw_content`.
- The current raw calendar path needs hardening around full Graph `$select`, source-quality, join URL policy, recurrence/timezone fidelity, project/source links, meeting-prep consumers, and access-event logging.

### Consumers currently starved or partially starved

| Consumer | Current source | Current blocker | Required fix |
|---|---|---|---|
| Daily brief email follow-ups | `email_followup_enrichments`, candidates, metadata summaries | structured/redacted enrichments may not consistently derive from persisted raw rows | policy-aware raw email read model with source-quality precedence |
| Daily brief meeting prep | `meeting_prep_brief_sections`, `calendar_event_index`, relationships | redacted/metadata sections lack agenda/body/attendee detail unless raw event rows are joined | meeting-prep context projection from `calendar_event_raw_content` |
| Local model context packets | `raw_content_model_context_packets`, local AI builders | needs explicit raw inclusion logging and packet boundedness | model-context packet builder with access audit rows |
| Relationship extraction | email/calendar/document relationship candidates | weak signals if body, attendees, thread context missing | full raw thread/event context projection and scoring inputs |
| Search/retrieval | redacted summaries, parser excerpts, metadata marts | email retrieval helper was removed for schema compatibility; calendar content shallow | raw-aware private retrieval read models, redacted outward |
| Status/diagnostics | receipts/status JSON | raw row counts/source-quality not surfaced enough | count/null-rate/source-quality diagnostics only |

## Target architecture

### Storage principle

Local private SQLite may store email/calendar business content when raw mode is explicitly enabled. Redaction belongs at outbound boundaries.

### Recommended schema strategy

Implement an additive next migration after current head, expected **V47** unless repo head has advanced.

Do not destructively alter old tables. Legacy redacted/metadata tables remain intact.

Add or backfill, idempotently:

- `source_quality` to `email_message_raw_content` with allowed values:
  - `graph_full_body`
  - `graph_body_preview_only`
  - `redacted_legacy_projection`
  - `metadata_only`
- `source_quality` to `email_thread_raw_context`.
- `source_quality` to `calendar_event_raw_content` with allowed values:
  - `graph_full_event_body`
  - `graph_body_preview_only`
  - `redacted_legacy_projection`
  - `metadata_only`
- `source_record_ref` / `source_record_id` bridge columns where the current schema lacks durable linkage.
- `raw_capture_run_id`, `captured_at_utc`, `payload_hash`, `source_updated_at_utc`, `raw_content_schema_version` where missing.
- Optional `email_calendar_raw_ingestion_runs` receipt table for bounded raw ingestion runs.
- Optional `raw_content_source_quality_snapshots` table for diagnostics.

Use additive `ALTER TABLE ADD COLUMN` guarded by `PRAGMA table_info`, or `CREATE TABLE IF NOT EXISTS` only. No destructive migrations.


### Structured projection target

Add final structured projection tables after raw capture. The exact names may follow repo convention, but the implementation must provide the following logical layer:

Email:

- structured message projection table;
- structured thread projection table;
- recipient child/detail table;
- attachment metadata child/detail table;
- message/thread bridge or equivalent refs;
- projection run/coverage receipts.

Calendar:

- structured event projection table;
- attendee child/detail table;
- recurrence child/detail table or documented lossless recurrence sidecar;
- location/online-meeting child/detail table or documented lossless sidecar;
- meeting-context projection for meeting prep;
- projection run/coverage receipts.

These structured projection tables are what daily brief, meeting prep, local model packet builders, relationship extraction, and private retrieval should consume. They may link back to raw rows for local-private context, but normal consumers should not directly spelunk raw JSON.

### Email raw ingestion design

- Fetch message list metadata with existing bounded folder/window controls.
- Fetch full message body only when local raw storage is enabled and bounded by `max_body_retrieval_per_run` / operator flag.
- Persist subject, preview, text/html body, sender/recipient/cc/bcc metadata, sent/received times, conversation IDs/hashes, attachment metadata, source refs, project refs, source quality, and hashes.
- Preserve body text and body HTML as provided by Graph; derive text from HTML only if needed and clearly mark it as derived.
- Build thread-level raw context from persisted message rows, not only from in-memory message lists.
- Use source-quality precedence: never let `metadata_only`, `redacted_legacy_projection`, or `graph_body_preview_only` overwrite `graph_full_body` unless the source record is newer and full body remains present.

### Calendar raw ingestion design

- Fetch calendarView metadata in bounded windows.
- For raw mode, fetch full event by ID with explicit `$select` covering subject, body, bodyPreview when available, attendees, organizer, location/locations, onlineMeetingProvider, onlineMeeting/join URL, recurrence, start/end/time zones, transaction IDs where available, sensitivity, categories, created/lastModified, cancellation state.
- Persist the full event content into `calendar_event_raw_content` under policy.
- Preserve join URL locally only if raw DB policy allows it; never emit join URLs to evidence/logs/stdout.
- Add source quality and precedence so metadata-only event rows cannot overwrite full event rows.

### Raw-content policy

Policy must distinguish:

- **DB-local storage**: may include raw email/calendar business content when explicitly enabled.
- **Outbound surfaces**: redacted by default.
- **Model context**: raw inclusion must be explicit, bounded, logged, and packetized.
- **Access audit**: raw reads must write `raw_content_access_events` except inside tests using isolated fixtures.

### Outbound safety

Raw bodies must not be emitted to:

- repo evidence;
- stdout;
- logs;
- browser/status JSON;
- Obsidian;
- daily brief output unless explicitly raw-intended and policy-gated;
- committed test snapshots;
- raw model prompts/responses persisted in SQLite;
- vector stores as raw text unless a separate explicit raw-vector policy is implemented.

Evidence may contain only counts, field names, hashes, source-quality distributions, null-rate deltas, pass/fail classifications, synthetic fixture text, and redacted examples.

## Prompt execution order

Run the prompts in order. Do not skip the repo-truth guard. The `04A`–`04D` prompts are mandatory and exist specifically to prevent the agent from stopping at raw capture.

1. `prompts/00_REPO_TRUTH_AND_BRANCH_GUARD.md`
2. `prompts/01_SCHEMA_AND_POLICY_STRATEGY.md`
3. `prompts/02_EMAIL_FULL_RAW_INGESTION.md`
4. `prompts/03_CALENDAR_FULL_RAW_INGESTION.md`
5. `prompts/04A_RAW_FIELD_INVENTORY_AND_PROJECTION_MATRIX.md`
6. `prompts/04B_STRUCTURED_PROJECTION_SCHEMA.md`
7. `prompts/04C_PROJECTION_REGISTRY_AND_EXTRACTORS.md`
8. `prompts/04D_IMPLEMENT_FINAL_STRUCTURED_PROJECTIONS.md`
9. `prompts/04_THREAD_AND_MEETING_CONTEXT_PROJECTION.md`
10. `prompts/05_CONSUMER_READ_MODELS_AND_MODEL_CONTEXT.md`
11. `prompts/06_OUTBOUND_REDACTION_AND_ACCESS_AUDIT.md`
12. `prompts/07_DB_COPY_VALIDATION_AND_EVIDENCE.md`
13. `prompts/08_FINAL_HANDOFF.md`

## Hard safety rules

Stop and ask Bobby before proceeding if any of these become true:

- Full email/calendar body storage requires a destructive schema migration.
- Implementation requires storing OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside the specifically approved local DB policy, or credential-cache contents.
- Raw content would need to be emitted to Git, stdout, logs, Obsidian, committed fixtures, or repo evidence to validate behavior.
- Production DB mutation is required for audit or validation.
- Graph scopes are insufficient and the fix requires new tenant/admin consent beyond currently configured runtime scopes.
- Raw retrieval would materially increase API cost/rate-limit risk without an operator-controlled bound.

## Required validation

Validation must include fixture-backed tests and `/tmp` DB-copy validation.

At minimum prove:

- full email body content persists to local SQLite when raw mode is enabled;
- full calendar body content persists to local SQLite when raw mode is enabled;
- raw field inventory exists for email/calendar raw tables and nested JSON paths;
- projection matrix maps every observed primary and nested business field to a final structured destination or explicit exclusion;
- final structured email projections are populated from `email_message_raw_content` and `email_thread_raw_context`;
- final structured calendar projections are populated from `calendar_event_raw_content`;
- unmapped primary business fields equal zero for every source family with available raw rows;
- unmapped nested business fields equal zero for every source family with available raw rows;
- thread context is built from persisted full email body data;
- meeting prep/read-model context can access full calendar body data;
- legacy redacted/preview rows cannot overwrite full raw rows;
- raw access events are recorded;
- outbound CLI/status/evidence surfaces do not emit raw bodies;
- no tokens/secrets are stored;
- production DB is untouched during validation.

Run this package's probe script only against a copied DB or let it create the copy:

```bash
python docs/planning/email_calendar_full_raw_content_ingestion_package/scripts/email_calendar_raw_probe.py \
  --repo /Users/bobbyfetting/hb-personal-assistant \
  --output /tmp/email-calendar-raw-probe.json
```

And run the projection inventory helper against the `/tmp` copy:

```bash
python docs/planning/email_calendar_full_raw_content_ingestion_package/scripts/email_calendar_raw_projection_inventory.py \
  --db /tmp/<copied-db>.sqlite \
  --out /tmp/email-calendar-raw-field-inventory.csv
```

If the implementation adds CLI surfaces, run the equivalent local commands:

```bash
hb-assistant email-calendar raw projection-inventory --db /tmp/<copied-db>.sqlite --json
hb-assistant email-calendar raw projection-reprocess --db /tmp/<copied-db>.sqlite --apply --json
hb-assistant email-calendar raw projection-coverage --db /tmp/<copied-db>.sqlite --json
```


## Evidence expectations

Evidence must live in repo under a new evidence directory, but must not contain raw email/calendar bodies.

Recommended evidence path:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/
```

Evidence files should include:

- repo state and branch guard;
- schema diff summary;
- test matrix summary;
- fixture proof;
- `/tmp` DB-copy probe output summary;
- raw field inventory and projection matrix;
- structured projection row-count, null-rate, and unmapped-field reports;
- no-leak scan output;
- operator runbook draft;
- final handoff.

Use `templates/evidence_template.md`.

## Production runbook expectations

Use `templates/operator_production_runbook_template.md` and include:

- config flags required to enable raw local storage;
- dry-run commands;
- apply commands;
- expected count/null-rate/source-quality diagnostics;
- rollback/disable steps;
- how to prove production DB was only mutated during the intentional apply run, not during audit/validation.

## Final handoff format

The final response from the local code agent must include:

```text
Branch / HEAD:
Commits:
Schema head before / after:
Files changed:
Tests run:
DB-copy validation summary:
No-leak proof summary:
Raw-content source-quality distribution:
Structured projection coverage summary:
Unmapped primary/nested business field counts:
Consumer before/after summary:
Production runbook path:
Evidence path:
Known limitations / deferred items:
Exact commands Bobby should run next:
```
