# 178 — Daily Brief V2 Packet Contract (Phase 09 Addendum, Prompt 01)

## Context

The Daily Brief V1 handoff packet (`DailyBriefHandoffPacketV1`) proved the
packet → MCP handoff → Claude rendering → receipt chain, but its single flat structure mixes
**internal governance metadata** (source-coverage metrics, guardrails, proof/receipt internals,
per-item provenance hashes) with the **data rendered into the brief body**. The Prompt 00 rebaseline
documented the resulting executive-utility defects (governance commentary and provenance leaking into
the rendered brief; source coverage dominating; count-only tables).

Prompt 01 introduces `DailyBriefHandoffPacketV2`, which splits the packet into two top-level halves so
governance can never render into the brief body. This is a **contract-only** change: it establishes the
shape, builder, proof, CLI, and tests. Content enrichment (calendar agenda, deadlines, email activity,
descriptive project activity) and the rendering rewrite land in later prompts.

## Design

### Two-half packet
- `render_payload` — user-facing, brief-ready data only: `brief_date`, `portfolio_scope`,
  `yesterday`, `today_agenda`, `next_7_days`, `needs_attention`, `focus_recommendations`,
  `project_signals`, `email_activity`, `calendar_activity`, `data_gaps`.
- `governance_metadata` — `packet_id`, `packet_version`, `generated_utc`, `brief_date`, `mode`,
  `source_coverage_summary`, `source_refs`, `guardrails`, `rendering_instructions`, `proof_metadata`,
  `receipt_metadata`, `status`, `degradation_mode`.

A **separation invariant** (`FORBIDDEN_IN_RENDER_PAYLOAD`) asserts no governance key
(packet_id/hash, source coverage, guardrails, source refs, proof/receipt metadata) appears inside
`render_payload`. The proof enforces it.

### Projection over V1 (no new retrieval)
`build_daily_brief_packet_v2` calls the canonical `build_daily_brief_packet` (V1) and re-projects its
output via `_project_v2_from_v1`. V1 remains the single source-assembly path; V2 is a safe rendering
projection. The renderable-item shape (`_build_render_item`) carries the full required field set;
fields not yet sourced from the V1 retrieval path (`project_name`, `record_id`, `status`,
`responsible_party`, dates) are emitted as `null` and flagged via `detail_availability` — never
fabricated.

### Honest data gaps (deferred to Prompt 02)
The daily-brief retrieval layer does not expose calendar events (`calendar_event_index`), per-day email
activity (`email_messages`), or Procore record due/start/finish dates, and applies no date window. So
`yesterday`, `today_agenda`, `next_7_days`, `calendar_activity`, and `email_activity` are emitted as
**empty arrays with explicit `data_gaps` entries** (`_V2_DEFERRED_SECTIONS`) deferred to
**Prompt 02 — Record-Level Enrichment**. This is fail-closed/honest: V2 declares every section but
never invents content.

## Surfaces

- Builder/proof/constants/loader: `construction/second_brain/daily_brief/packet.py`
  (`PACKET_VERSION_V2`, `RENDER_PAYLOAD_SECTIONS`, `RENDER_ITEM_FIELDS`,
  `GOVERNANCE_METADATA_FIELDS`, `FORBIDDEN_IN_RENDER_PAYLOAD`, `RENDERING_INSTRUCTIONS_V2`,
  `build_daily_brief_packet_v2`, `build_daily_brief_packet_v2_proof`,
  `load_daily_brief_packet_v2_contract`).
- Contract resource: `resources/json/phase_09_daily_brief_handoff_packet_v2_contract.json`, registered
  in `contracts.py` as `daily_brief_handoff_packet_v2_contract`.
- CLI: `cli/second_brain.py` — `packet --version v1|v2` and new `packet-v2-proof`.
- Tests: `tests/test_phase_09_daily_brief_packet_v2.py`.
- Evidence: `docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2/`
  (`daily-brief-packet-v2-contract.{json,md}`, `daily-brief-packet-v2-proof.{json,md}`).

## Guardrails

Same as V1: advisory-only, source-linked, metadata-only, no raw, no external writeback, no
final-determinations, Claude-rendering-only. Read-only; persists nothing; fail-closed on missing
contract or raw leakage. V1 builder, proof, CLI default, and contract are untouched (additive).

## Addendum (v1.5.1-phase-09-addendum-v2) — top-level self-identification

The V2 packet now carries `packet_version = "DailyBriefHandoffPacketV2"` at the **top level** (it was
previously only inside `governance_metadata`, so the packet did not self-identify and could be confused
with V1). It is retained in `governance_metadata` (and `proof_metadata`) for provenance. The contract
adds `packet_version` to `top_level_keys` (contract version 1.2.0); it remains forbidden inside
`render_payload`. A reusable validator `is_daily_brief_packet_v2(packet)` (in `daily_brief/packet.py`,
exported from `daily_brief/__init__.py`) requires the top-level version plus the render/governance split
and rejects a V1 packet (or a V2 packet with the top-level version stripped). The V2 packet proof gains
`top_level_packet_version_present` + `missing_top_level_version_rejected`; the MCP handoff proof's
`packet_version_ok` now requires the top-level version; the MCP wrapper propagates it unchanged.
