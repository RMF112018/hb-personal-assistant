# 00 — Shared Context

## Objective

Implement a local Procore structured analytics foundation.

The objective is broader than daily-brief quality. The system must capture Procore endpoint data in structured, endpoint-family tables for future analytics, reporting, local retrieval, reprocessing, and operator drill-down. The daily brief and local model consume downstream ranked/redacted projections.

## Governing facts from the DB audit package

Carry these facts forward, then verify from repo truth and a fresh DB-copy audit:

- Schema version `45`.
- `procore_live_records`: `30,059` rows.
- `procore_live_record_snapshots`: `27,963` rows.
- `procore_live_record_change_events`: `29,738` rows.
- `procore_action_signals`: `5,866` rows.
- `procore_financial_amount_facts`: `85,525` rows.
- `daily_brief_action_candidates`: `0` rows.
- `candidate_source_refs`: `0` rows.
- `calendar_event_raw_content`: `117` rows.
- `email_message_raw_content`: `1` row.
- No equivalent Procore raw/structured raw-content family was present.

## Architecture principle

Use a layered model:

1. Capture/control receipts.
2. Governed raw payload landing/snapshots.
3. Structured endpoint-family bronze tables.
4. Normalized silver projections.
5. Gold/read-model surfaces for analytics, daily brief, local models, and operator CLI.

## Hard constraints

- No production DB mutation during audit/validation.
- No Procore writeback.
- No Graph/email/calendar/SharePoint/MCP writeback.
- No raw payloads or DB extracts in repo evidence.
- No cloud LLMs.
- No generic JSON-only storage as the final analytics answer.
- No raw leaks to daily brief, status JSON, Obsidian, browser output, tests, or evidence.

## Required behavior

Before each prompt, inspect repo truth. Do not guess. If repo truth conflicts with package language, follow repo truth and record the conflict in evidence.
