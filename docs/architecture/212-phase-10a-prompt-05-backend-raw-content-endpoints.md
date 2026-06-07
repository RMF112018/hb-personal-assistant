# Phase 10A Prompt 05 — Backend Raw Content Endpoints (2026-06-07)

**Status:** Implemented (additive, surgical).

## Objective

Expose raw-content-capable backend query "endpoints" (Python callables) for email and calendar so that local consumers (CLI query commands, meeting-prep packets, daily brief enrichment, future MCP/model-context builder in Prompt 06, etc.) can obtain the persisted raw plaintext (subject/body/participants/attendees/join etc.) when the raw_content policy + params allow, while the pre-existing metadata/redacted shapes and all no-raw surfaces remain fully available and unchanged.

## Tasks (as specified)

1. Add/extend email endpoints.
2. Add/extend calendar endpoints.
3. Add `include_raw` and `raw_mode` parameters (with policy resolution).
4. Default to raw inclusion when configured (per EndpointsConfig + default_endpoint_behavior).
5. Add endpoint tests.

## Acceptance

- Local API (new endpoint fns + CLI `graph mail threads` / `graph calendar events` --json surfaces) can return raw email/calendar content.
- Metadata/redacted mode remains available (explicit `raw_mode=metadata_only`, `include_raw=false`, or policy default).

All prior safety gates, no-raw proofs, redacted read models, and CHECK constraints are untouched.

## Key Changes

### Store (repositories.py)
- Added (additive) the missing email raw read accessors after the Prompt 03/04 upserts:
  - `list_email_message_raw_content(project_key, limit)` + JSON parse for recipients/attachment meta.
  - `get_email_message_raw_content(message_id_hash)`.
  - `list_email_thread_raw_context(project_key, limit)` + JSON parse for messages/source_refs.
  - `get_email_thread_raw_context(thread_ref)`.
- Calendar already had symmetric list/get from Prompt 04; email now matches for endpoint parity.
- All reads are project-filterable, bounded, and idempotent.

### New modules
- `src/hb_assistant/construction/email/endpoints.py`
  - Policy-aware list/get: `list_email_threads`, `list_email_messages`, `get_email_message`.
  - Direct raw accessors (gated): `list_*_raw_content`, `get_*_raw_content`.
  - Internal `_resolve_include_raw(include_raw, raw_mode)` that consults `load_raw_content_policy().raw_content`:
    - `enabled && mode in (email_calendar, all_supported, ...)` && `starting_sources.email`
    - `endpoints.allow_include_raw_param`
    - `endpoints.default_raw_mode` / `default_endpoint_behavior`
    - Explicit `raw_mode` > explicit `include_raw` > policy default.
  - When effective: base from `store.list_email_thread_summaries` / `list_email_messages` / `get_email_message`, then enrich by hash/thread_ref lookup into the raw tables and attach a stable `"raw_content"` sub-dict (or inlined fields) + `_raw_content_included` marker.
  - When not effective: exactly the prior redacted shape + marker=false (no raw keys leaked).

- `src/hb_assistant/construction/calendar/endpoints.py`
  - Analogous: `list_calendar_events`, `get_calendar_event` (base `list_calendar_event_index` + enrichment via `get_calendar_event_raw_content(event_index_id)`).
  - Direct gated raw list/get.
  - Same resolution contract (calendar source gate).
  - Centralizes the enrichment previously duplicated inline in `meeting_prep/brief_builder.py` (additive; existing direct store.get still works).

### Package surfaces (additive)
- `construction/email/__init__.py` and `construction/calendar/__init__.py`: export the new callables + `RawMode`.
- `construction/store/__init__.py`: additive comment noting the email raw accessors are on `ConstructionStore` (methods inherited; calendar precedent unchanged).

### CLI local-API evidence (graph.py)
- Added `@calendar_app.command("events")`:
  - `--include-raw`, `--raw-mode`, `--source`, `--limit`, `--json`.
  - Calls `list_calendar_events(...)` and emits the endpoint response shape.
- Added `@mail_app.command("threads")`:
  - `--include-raw`, `--raw-mode`, `--project`, `--limit`, `--json`.
  - Calls `list_email_threads(...)`.
- Existing index commands (`--include-raw-content`) untouched; these are the read/query counterparts.

### Contract + wiring
- `src/hb_assistant/resources/json/raw_content_api_response_contract.json`: declarative shapes for metadata vs raw-included responses for threads/messages/events + direct raw accessors + policy surface + invariants.
- `local_ai/contracts.py`: registered in `PHASE_10_CONTRACT_FILES`; `load_raw_content_api_response_contract()` wired (additive loader).
- `local_ai/proof.py`: imports + exercises the loader inside `build_phase_10_contracts_proof` so the contracts proof covers the new surface.

### Tests
- `tests/test_email_endpoints.py`: temp DB, seed raw + minimal meta, exercise list/get with/without raw flags, direct raw accessors, project filter, graceful no-row, single get.
- `tests/test_calendar_endpoints.py`: same for calendar; includes private/cancelled/online case (raw still carries content while index metadata remains limited).
- Updated `tests/test_phase_10_contracts.py`: bumped len assertion (12) and asserted presence of the new response contract.

### Docs
- `docs/architecture/212-phase-10a-prompt-05-backend-raw-content-endpoints.md` (this file).
- One-line append to `docs/architecture/00-README.md` under Phase 10A.

## Policy Integration (from Prompt 01)

The `RawContentSettings.endpoints` block (allow_include_raw_param, default_raw_mode) + top-level `default_endpoint_behavior` + `mode` + `starting_sources` fully control the query surface. The resolver is fail-closed on any load or mode mismatch. Explicit CLI flags are hints only.

This design ensures Prompt 06 (raw model context builder) and other downstreams can opt into raw via the same params without altering any metadata path or prior no-raw guarantees.

## Data Flow (read path)

```
CLI / packet / MCP caller
  -> list_email_threads(..., include_raw=..., raw_mode=...)
  -> _resolve_include_raw (policy load + gates)
  -> store.list_email_thread_summaries(...)   [always redacted base]
  -> if effective: store.list_email_thread_raw_context(...) + attach "raw_content"
  -> return list[dict] with marker + optional sub-dict
(same pattern for messages, calendar events)
```

Direct raw accessors short-circuit to []/None when not effective.

## Non-Goals / Scope (kept exact)

- No web service / FastAPI surface.
- Graph list paths remain metadata-only (raw captured only at index time under policy).
- Downstream allowances (MCP/Obsidian raw) remain prohibited for email_calendar per P01.
- No work on model-context builder (Prompt 06).
- No modification or deletion of prior tables/fields/CHECKs.
- No change to redacted read models or safety scans.

## Risks & Guardrails

- Endpoints never emit raw unless the full policy + effective flag chain passes (defense-in-depth with the V42 table exemptions).
- Hash linkage (message_id -> message_id_hash via redaction.hash_value) is internal to enrichment; callers see only the final combined shape or pure metadata.
- Tests + manual sims (via the new CLI --json paths) prove both modes and "no raw when excluded".
- All changes additive; prior index/upsert paths and no-raw proofs are bit-compatible.

## Verification Performed

(See runbook evidence in the commit; summary: ruff/format clean on touched files; mypy scoped green; pytest focused on email/calendar/endpoint/phase_10/raw/second_brain green; manual python -c + CLI --json runs against temp DB with seeded raw rows demonstrate include vs metadata modes; no leakage of bodies when excluded; contract proof includes the new response contract.)

## How This Enables Later Work

Prompt 06 (Raw Model Context Builder) and MCP/brief consumers can now request raw email/calendar packets via the documented include/raw_mode knobs, with the same policy surface and no impact on the metadata-only default posture or existing proofs.

## References

- Prompt 01 (config/policy + EndpointsConfig)
- Prompt 02 (V42 schema)
- Prompt 03 (email raw ingestion + upserts)
- Prompt 04 (calendar raw ingestion + store list/get + brief enrichment)
- `resources/config/phase_10a_raw_content_policy.seed.yaml`
- `src/hb_assistant/resources/json/phase_10a_raw_content_policy_contract.json`
- `src/hb_assistant/resources/json/raw_content_api_response_contract.json`
- Related ADRs: 208–211 under docs/architecture/

Minimal pointer (surgical). All changes limited to the listed files + new endpoint modules/tests/doc.