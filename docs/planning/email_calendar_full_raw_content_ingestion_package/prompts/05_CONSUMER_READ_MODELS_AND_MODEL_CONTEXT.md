You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 05 — Consumer Read Models and Model Context

## Objective

Wire downstream consumers to prefer raw-aware private read models while preserving redacted outbound surfaces by default.

## Consumer targets

Audit and update the current repo-truth locations for:

- daily brief email follow-ups;
- daily brief meeting prep / agenda usefulness;
- local model context packet builders;
- relationship extraction/scoring;
- search/retrieval;
- project-source linking;
- status/diagnostics.

Likely paths include:

```text
src/hb_assistant/construction/second_brain/local_ai/raw_context.py
src/hb_assistant/construction/second_brain/local_ai/packet_builders.py
src/hb_assistant/construction/second_brain/local_ai/raw_followup_window.py
src/hb_assistant/construction/meeting_prep/brief_builder.py
src/hb_assistant/construction/email/endpoints.py
src/hb_assistant/construction/calendar/endpoints.py
```

## Required behavior

1. Add read models that expose safe structured context objects, not raw strings by default.
2. Source precedence must prefer:
   - email: `graph_full_body` > `graph_body_preview_only` > `redacted_legacy_projection` > `metadata_only`;
   - calendar: `graph_full_event_body` > `graph_body_preview_only` > `redacted_legacy_projection` > `metadata_only`.
3. Model context packets may include raw content only when explicit and bounded.
4. Every raw model-context inclusion must persist a `raw_content_model_context_packets` row indicating:
   - packet ID;
   - source family;
   - source refs/hashes;
   - raw included flag;
   - source quality distribution;
   - truncation/bounds;
   - model purpose;
   - policy version.
5. Raw reads must write `raw_content_access_events` with no raw body in the event row.
6. Daily brief and Obsidian outputs remain redacted by default.

## Tests

- Raw-aware read models select full raw rows when available.
- Degraded/metadata-only states are honest.
- Model packet creation logs raw inclusion and bounds.
- Daily brief / meeting prep outputs improve using raw-derived summaries without leaking raw body strings.
- Status JSON includes counts/source-quality/null-rates, not raw content.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/05_consumer_read_models_and_model_context.md
```

## Mandatory source precedence

Consumer read models must prefer the final structured projection layer, not the raw landing tables and not the legacy metadata/redacted tables.

Required precedence:

1. final structured projection row sourced from `graph_full_body` / `graph_full_event_body`;
2. final structured projection row sourced from preview-only raw content;
3. legacy redacted/metadata projections;
4. no content available.

Every daily brief, meeting prep, local model packet, relationship extraction, and private retrieval path touched by this package must make this precedence testable. A consumer that can still silently select a stale/redacted legacy row when a complete structured projection exists fails this package.
