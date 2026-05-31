# Phase 07B — Calendar & Email-Thread Intelligence Foundation (Schema + Source Registry)

**Phase:** 07B — Prompt 02 (Calendar Schema And Source Registry)
**Status:** Implemented (schema + policy foundation; ingestion/matching/summary logic land in 07B Prompts 03–09).
Evidence: `docs/evidence/construction-intelligence-phase-07b-calendar-email/02-schema-and-migration-proof.md`.

This record documents the additive schema and policy foundation for calendar and email-thread
intelligence. It is the structural base the later 07B prompts populate; this prompt adds **no
ingestion, matching, or summarization logic** and performs no external calls.

## Schema — migration V23

`store/migrator.py` adds `v23_calendar_email_thread_intelligence` (`LATEST_SCHEMA_VERSION = 23`),
additive `CREATE TABLE/INDEX IF NOT EXISTS` only; V1–V22 untouched (including the V20/V22 raw-body
guardrails). Eight tables:

| Table | Role | Guardrails |
|---|---|---|
| `calendar_source_locations` | calendar source registry | `read_only = 1` (immutable CHECK) |
| `calendar_sync_state` | bounded per-source sync state | `error_redacted` only |
| `calendar_crawl_runs` | crawl receipts | raw_body / full_text / external_writeback = 0 |
| `calendar_event_index` | redacted event materialization (project + review fields) | raw_body / full_text / external_writeback = 0; UNIQUE(source_id, graph_event_id_hash); 3 indexes |
| `calendar_event_attendees` | attendee hash/domain only | UNIQUE(event_index_id, attendee_hash) |
| `calendar_project_match_candidates` | event→project candidates | raw_body / external_writeback = 0; default review_required, promotion_status='candidate' |
| `meeting_email_relationship_candidates` | event→thread candidates | raw_body / raw_prompt / raw_response / external_writeback = 0; 2 indexes |
| `email_thread_summary_materialization_runs` | thread-summary receipts | raw_body / raw_prompt / raw_response / external_writeback = 0 |

All identifying values (subject, organizer, location, web link, iCal UID, attendees, thread keys)
are stored **hashed or redacted only**. The legacy `calendar_events` (V1) and `email_thread_summaries`
(V11) tables are intentionally left unchanged — the V23 tables are the 07B model.

## Policy + contracts

The complete 07B policy/contract foundation is shipped now (consumed by later prompts):

- YAML policy seeds under `resources/config/` (filesystem-resolved via `PathPolicy`, like the
  existing construction/email seeds): `calendar_source_policy.seed.yaml`,
  `email_thread_summary_policy.seed.yaml`, `review_required_calendar_email_rules.seed.yaml`.
- JSON contracts under `src/hb_assistant/resources/json/` (importlib-resolved, like the data-quality
  resources): `calendar_project_match_contract.json`, `email_thread_summary_contract.json`,
  `meeting_email_relationship_candidate_contract.json`.

Loaders live in the new `construction/calendar/` subpackage (`policy.py`, `contracts.py`). The
Pydantic policy models **enforce safety invariants at load time**: calendar sources are read-only,
event body / join URL are never persisted, and decrypted body / raw prompt / raw response are never
persisted; the JSON contract loaders assert auto-promotion is disabled. A seed that violates these
raises rather than loading.

## Repository helpers

`ConstructionStore` (`construction/store/repositories.py`) gains source-registry write helpers in the
established kw-only / `INSERT … ON CONFLICT` style: `upsert_calendar_source_location` (rejects any
non-read-only source, mirroring `upsert_source_location`) and `upsert_calendar_sync_state`. Helpers
for the event-index / candidate / summary-run tables are deferred to their feature prompts.

## Guardrails

No external (M365/Procore/SharePoint/OneDrive/Outlook/calendar) mutation or writeback. V23 is a local
additive migration; the registry helper writes only local SQLite and refuses writeback-capable
sources. No raw body, prompt, response, token, secret, signed URL, raw delta link, or private value
appears in schema, seeds, contracts, code, or tests. No Phase 07D meeting-prep readiness is claimed;
07D remains blocked. `data-quality table-inventory` classifies the eight new tables via the updated
lifecycle contract; `no-writeback-proof` (07A-scoped) is unaffected and the 07B-scoped safety proof
remains Prompt 12.
