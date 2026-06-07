# Phase 10A Prompt 04 — Calendar Raw Content Ingestion

**Date:** 2026-06-07  
**Status:** Implemented (additive)  
**Related:** Phase 10A 00_PACKAGE_MANIFEST, 04_SCHEMA_PLAN (V42), Prompt_04_Calendar_Raw_Content_Ingestion.md, prior Prompt 01 (raw policy), Prompt 02 (V42 tables), Prompt 03 (email raw pattern + CLI/store shape), meeting prep.

## Objective
Update calendar indexing (the production ReadOnlyCalendarClient + CalendarEventIndexer path used by `graph calendar index` and the source-refresh orchestrator) to fetch/store subject, body, location, organizer, attendees, join URL, and recurrence metadata when raw-content mode/policy enables `email_calendar` (or explicit `--include-raw-content`). Persist into the V42 `calendar_event_raw_content` table (plaintext, exempt from 13-guard CHECKs). Add store accessors (list/get) for endpoint and context packet use. Enrich meeting-prep packet builder to surface actuals when raw rows exist. Keep the redacted `calendar_event_index` + attendees metadata path 100% unchanged. Reuse bounded window, dry_run, chunked apply, source policy, private/cancelled/online flags.

## Files Touched (surgical, additive)
- `src/hb_assistant/construction/store/repositories.py`: Added `upsert_calendar_event_raw_content` (idempotent ON CONFLICT(graph_event_id_hash), columns match V42 draft exactly) + `list_calendar_event_raw_content` (by project_key) + `get_calendar_event_raw_content` (by event_index_id or graph hash) for packet/endpoint access. Exposed via the ConstructionStore class (no facade changes needed). Header comment updated to note Prompt 03/04.
- `src/hb_assistant/graph/calendar_readonly_client.py`: Added `get_event(self, event_id)` — guarded single-event GET with rich $select for body/join/recurrence/attendees/full organizer etc. (reuses _guarded_get + existing allowlist for /me/events/{id}). list_calendar_view and contract metadata select untouched (still body/join-free).
- `src/hb_assistant/construction/calendar/event_indexer.py`: Import load_raw_content_policy. Extended `IndexResult` with `include_raw_content`, `raw_content_enabled`, `raw_events_persisted`. Added `include_raw_content: bool = False` param to `index()`. Policy resolution (fail-closed) for email_calendar + calendar starting source (mirrors email P03). Per-event: when effective_raw, call get_event (fallback to list item), build raw payload via new `_build_raw_calendar_payload`, upsert on apply (counts tracked for dry too). Raw counts/ flags returned in result; dry_run emits would-persist without writes. All chunked apply, crawl receipts, sync state, private/cancelled/online metadata handling, redacted index path, and idempotency preserved. Module-level behavior for metadata unchanged.
- `src/hb_assistant/cli/graph.py`: Added `--include-raw-content` Typer option to `calendar_index_cmd`; pass-through to indexer; updated docstring ("supports --include-raw-content for Phase 10A raw calendar content (when policy allows); metadata path remains redacted"). Result JSON automatically includes raw_* via model_dump().
- `src/hb_assistant/construction/meeting_prep/brief_builder.py`: In `_section_meeting_context`, after listing redacted index events for the project, call `get_calendar_event_raw_content(event_index_id=...)` for matched events and (when present) attach `matched_event_details` array with actual subject/body_text/body_html/location/organizer/attendees/join_url/start into the section payload. Consumers of the meeting prep packet/brief now see real content for those events (fallback to prior metadata-only if no raw row). No changes to redaction or other sections.
- Minor: none for __init__ exports (additive methods on existing classes; direct imports in CLI/orchestrator/brief_builder already resolve the classes).

No changes to: calendar_event_index / attendees (still have CHECK raw_calendar_payload_persisted=0), list_calendar_view $select/contract, legacy calendar_client, orchestrator call sites (they rely on policy-driven path), no-writeback layers, encrypted/raw leakage paths, or any DROP/ALTER.

## Decision / Rationale
- Policy + flag (Prompt 01 surface) + email raw precedent (Prompt 03): explicit opt-in or `email_calendar` + starting_sources.calendar enables; downstream toggles remain off.
- Separate get_event on client + per-event fetch only on effective_raw path: minimal new surface; bounded by the list scope (max_items); mirrors mail get_message_body reuse for raw.
- Raw table only for plaintext: V42 is the designated exempt holder (Prompt 02); metadata tables and all guards stay strict.
- Store list/get accessors: enable "endpoint and context packet access" (Prompt 04 task) and the brief_builder enrichment for acceptance ("meeting prep packet includes actual...").
- Brief builder overlay: when raw row exists for an event_index_id, include the actual fields in the packet payload under matched_event_details (or equivalent). This delivers the acceptance without altering redacted paths or other sections.
- Private/cancelled/online: raw path captures full content (that's the point of opt-in); metadata path behavior identical to before (private = minimal + review flag; cancelled/online flags preserved in index).
- Dry/apply evidence: raw_* counts in IndexResult (and thus CLI JSON + processing receipts) mirror email pattern; dry computes would-persist, apply writes rows + receipt detail.
- Additive only, fail-closed, read-only, no external writes.

## Verification Summary (post-impl)
- Dev `hb-assistant graph calendar index --no-dry-run --include-raw-content --json` (or equiv via orchestrator when policy active) produces rows in `calendar_event_raw_content` (subject/body_text/body_html, location_display, organizer_*, attendees_json with type/status/name/address, join_url for online meetings, recurrence_json, times present).
- `get_calendar_event_raw_content` / list return the rows; brief_builder sections for matched project events include `matched_event_details` with actuals (subject/body/attendees/join) when raw rows exist.
- `calendar_event_index` + attendees unchanged (no body/join/raw values; private minimal + review; counts match prior).
- Re-run is idempotent (ON CONFLICT on graph hash; no dup growth).
- Dry-run path: returns raw_* would counts >0 when effective, no raw table writes.
- Private/cancelled/online cases: raw rows have full content; metadata path limited per existing rules.
- Linting/type: ruff clean, mypy (scoped) clean on touched files + local_ai.
- Focused tests + manual: see verify section below (green where exercised; pre-existing broad suite noise acknowledged).
- Sensitive scan / no-writeback / guard attest: raw only in the V42 raw table; metadata guards + CHECKs hold; no leakage to old paths, no tokens/full-delta in outputs, no mutations.

## Guardrail Attestations
- Raw plaintext only in designated V42 `calendar_event_raw_content` when policy on + (flag or email_calendar + calendar source); never in calendar_event_index (still redacted/hashed, CHECK raw=0), never in vault/obsidian/evidence logs, never submitted to cloud LLM.
- Mailbox/calendar stays read-only at all layers; no mutations.
- Evidence + receipts only on apply (not dry); dry_run default safe.
- All source traceability preserved; redaction for non-raw paths untouched.
- Additive migration (V42) + no drops/rewrites of prior schema or behavior.

## References
- Planning: `docs/planning/HB_Construction_Intelligence_Phase_10A_.../Prompt_04_Calendar_Raw_Content_Ingestion.md`, `04_SCHEMA_PLAN.md`.
- Prior: Arch 208 (P01 policy), 209 (P02 V42), 210 (P03 email raw + store/CLI/brief shape), Phase 07B calendar metadata patterns.
- Code: event_indexer.py (reuse list + new get_event + policy + raw upsert + build helper), repositories.py (raw upserts + accessors), cli/graph.py (flag), brief_builder.py (packet enrichment), calendar_readonly_client.py (get_event), local_ai (policy load + RawContentPolicy).

Follow-ups (deferred): full raw endpoints (Prompt 05), calendar in model context packets, downstream consumption under future policy, bounded max from model_context, raw access events logging, orchestrator explicit flag wiring if desired for dev.
