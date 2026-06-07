# Phase 10A Prompt 06 — Raw Model Context Builder (2026-06-07)

**Status:** Implemented (additive).

## Objective

Build model-ready raw email/calendar context packets that carry actual (plaintext) content from the Phase 10A V42 raw tables (`email_message_raw_content`, `email_thread_raw_context`, `calendar_event_raw_content`) when the `RawContentPolicy.raw_content.model_context.include_raw_content` (and starting source) allows, with strict bounds, source references, and persistence for local model consumption / replay.

## Tasks Completed

1. Packet builders implemented in `src/hb_assistant/construction/second_brain/local_ai/raw_context.py`:
   - `build_raw_email_context_packet(...)` — pulls via P05 `list_email_threads(..., include_raw=True)` (or direct raw), applies `max_threads_per_run` / `max_messages_per_thread` / `max_body_chars_per_message`, truncates bodies, assembles `content.threads[].messages` with actual subject/body/from/to, collects source refs (message_id_hash + thread_ref), computes rough token_estimate (chars/4), persists to `raw_content_model_context_packets`, returns envelope.
   - `build_raw_calendar_context_packet(...)` — analogous for events (max_events, max body chars), includes location/organizer/attendees/join_url/start/end/recurrence + actual body.

2. Bounded packet sizes — directly from `ModelContextConfig` (populated in the P01 policy seed).

3. Source refs — stable hashes + row identifiers (event_index_id, graph_event_id_hash, thread_ref, message hashes) carried in the packet and the persisted row's `source_ref_hash` column.

4. CLI commands added under the existing `phase-10` Typer group in `cli/second_brain.py`:
   - `second-brain phase-10 raw-email-packet --project P [--json]`
   - `second-brain phase-10 raw-calendar-packet --project P [--json]`
   Both call the builders and emit the full packet (or error envelope). Exit codes 0/1 as other phase-10 commands.

5. Fixture tests in `tests/test_phase_10a_raw_model_context_packets.py`:
   - Seed raw rows directly (via the known V42 upserts).
   - Assert actual content present in returned packet and persisted `packet_json`.
   - Assert source refs, token_estimate > 0, bounds respected (truncation).
   - Graceful metadata-only packet (raw_content_included=0, empty content) when policy/model_context disallows.
   - Persistence verified via `store.list_raw_content_model_context_packets`.

## Store Additions (additive)

- `upsert_raw_content_model_context_packet(...)` (idempotent on packet_id, writes the 9 columns per V42 DDL).
- `list_raw_content_model_context_packets(...)` (project/packet_type filter, bounded).

These live in the Phase 10A raw-content section of `repositories.py` (after the P03/P04 raw list/get, before the V20 data-quality block).

## Policy Surface

Builders consult `load_raw_content_policy().raw_content.model_context` (include_raw_content + the five max_* fields) + the top-level `enabled`/`mode`/`starting_sources`. When not effective they emit (and persist) a safe empty metadata-only packet with `raw_content_included=0`. This is orthogonal to the P05 endpoint `include_raw`/`raw_mode` (endpoints are for query surfaces; P06 is the model-context consumer).

The P01 `DownstreamToggles.mcp_allow_raw_content` / `obsidian_allow_raw_content` remain false for `email_calendar` (enforced in the policy validator); P06 is the sanctioned local-model-context path.

## Data Model (V42)

`raw_content_model_context_packets`:
- packet_id (PK), packet_type ("raw_email_context" | "raw_calendar_context"), source_family, source_ref_hash, project_key, raw_content_included (0/1), packet_json (the full envelope), token_estimate, created_utc.

A companion `raw_content_access_events` table exists for future audit of who consumed which packet (not wired in P06).

## Acceptance Mapping

- `hb-assistant second-brain phase-10 raw-email-packet --json` produces a packet whose `content.threads[*].messages[*].body_text` etc. contain the seeded actual plaintext (when policy permits).
- Same for `raw-calendar-packet` (body, join_url, attendees, etc.).
- Packets are bounded and carry source refs.
- Packets are persisted (listable via store or future CLI).
- When policy/model_context disallows raw, packets are metadata-only (no leakage).

## Non-Goals / Scope

- No change to the "no raw" guarantees on daily-brief/research/MCP handoff packets (those remain metadata-only by design).
- No external LLM submission (still prohibited).
- No changes to Graph clients or ingest paths.
- Prompt 03 (local model runtime provider) remains incomplete (provider.py exists as WIP but has no CLI/tests; explicitly excluded here).

## Verification

- ruff/format + mypy (scoped to new + touched files) clean.
- Focused pytest on the new test file + phase_10* + raw* + local_ai + second_brain (green).
- Manual: temp DB, seed raw rows, run the two CLI commands with --json, observe actual content, source refs, token_estimate, and rows in the packets table.
- CLI under `phase-10` group (alongside contracts-proof / schema-status).

## Risks / Guardrails

- The raw packets are the intentional exception to the "no plaintext body" rule for the local model context path only. All other surfaces (daily brief, research, synthesis receipts, safety gates, etc.) continue to enforce no-raw.
- Bounded by policy config (fail-closed if policy load fails).
- Source refs are hashes + stable keys (never raw Graph ids or tokens).

## References

- P01: policy + ModelContextConfig + EndpointsConfig.
- P03/P04: raw ingestion + V42 tables + store list/get + P05 endpoints.
- P05: the query surface that P06 consumes.
- V42 DDL in migrator (raw_content_model_context_packets + access_events).
- Arch 208–212 (prior Phase 10A ADRs) + this 213.
- table_lifecycle_status_contract.json (the 6 V42 tables).

Minimal/surgical. All changes additive. The V41 action tables (Prompt 02 reconciliation) and V42 raw tables coexist as required.

Next free arch number after this run: 214 (verify before next doc).