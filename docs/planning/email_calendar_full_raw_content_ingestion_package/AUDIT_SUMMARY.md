# Audit Summary — Email + Calendar Full Raw Content Ingestion

## Concise verdict

The repo has the right foundational schema direction but not a complete, production-quality raw email/calendar content system.

- V42 introduced designated plaintext raw tables for email messages, email threads, calendar events, raw model context packets, policy state, and access events.
- Older operational email/calendar pipelines remain intentionally redacted/metadata-only.
- Current Phase 10A raw branches exist in `message_indexer.py` and `event_indexer.py`, but require hardening before they can be treated as the private local DB system of record.
- Downstream daily brief, meeting prep, retrieval, relationship extraction, and model-context consumers still need deterministic raw-aware read models and outbound redaction gates.

## Existing schema

Current schema head observed: **V46**.

Raw-content tables exist:

```text
raw_content_policy_state
email_message_raw_content
email_thread_raw_context
calendar_event_raw_content
raw_content_model_context_packets
raw_content_access_events
```

Key gap: source quality is not yet a first-class acceptance gate on all raw rows. Additive migration recommended.

## Email bottlenecks

- Older graph/mail client list paths select `bodyPreview` only.
- Older store facade persists `emails` rows with metadata only.
- V11 `email_messages` remains preview/redacted-only with full-body CHECK guards.
- V12 encrypted body vault reference does not give SQLite-local plaintext body context.
- Current raw email indexer branch fetches body and writes raw rows only when effective raw mode is enabled; it still needs source-quality, precedence, access audit, source-link, project-link, and consumer-hand-off hardening.

## Calendar bottlenecks

- Older graph/calendar client selects metadata only and omits full body, attendees, recurrence, and full online meeting payload.
- V23 `calendar_event_index` persists hashed/redacted metadata only.
- Current raw event indexer branch calls `get_event()` and writes raw rows only when effective raw mode is enabled; it still needs explicit Graph `$select`, source-quality, join URL policy, recurrence/time-zone completeness, access audit, project/source linkage, and meeting-prep handoff hardening.

## Consumer bottlenecks

- Daily brief follow-up usefulness is constrained when it reads redacted enrichment tables instead of full raw email/thread context.
- Meeting prep remains thin when it reads `calendar_event_index` metadata and redacted meeting-prep sections instead of agenda/body/attendee content.
- Model context packets need explicit raw inclusion logging and bounded payload design.
- Relationship extraction needs persisted raw thread/event context as inputs, not only metadata/hashes.
- Search/retrieval needs private raw-aware read models while keeping outward answers redacted unless explicitly allowed.

## Required implementation direction

Implement an additive migration and controlled ingestion/consumer changes:

1. Add source-quality and source-ref columns/receipts where missing.
2. Harden email raw ingestion and raw thread context projection.
3. Harden calendar raw ingestion and meeting-prep projection.
4. Build consumer read models that prefer full raw rows by source-quality but output redacted summaries by default.
5. Log raw access events and model packet raw-inclusion status.
6. Prove no raw leakage to repo evidence/stdout/logs/status/Obsidian/test snapshots.
7. Validate on fixtures and a `/tmp` DB copy only.

## Addendum — Structured Projection Gap

The stronger Procore endpoint-specific package pattern applies here as well: raw capture alone is incomplete. Email/calendar raw rows must be transformed into final structured projections that are queryable by the daily brief, meeting prep, local model, relationship, and retrieval layers.

The added `04A`–`04D` prompts force the local agent to:

- inventory all available raw email/calendar columns and nested JSON paths;
- build a projection matrix;
- implement additive structured projection tables;
- implement projection registry/extractors;
- prove zero unmapped primary and nested business fields for source families with available raw rows.
