# 170 — Phase 09 Addendum: Daily Brief Handoff Packet (DailyBriefHandoffPacketV1)

**Status:** New read-only surface — a stable, metadata-only daily-brief packet Claude can safely consume through MCP for rendering only.
**Schema:** unchanged (V39; **no migration**; persists nothing). **Version:** 1.0.0-phase-09-addendum (package: Daily Brief / MCP Handoff & Rendering, Prompt 01).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/daily-brief-packet-contract.{json,md}` + `daily-brief-packet-proof.{json,md}`.
**Builds on:** record 08 (daily brief module), the Phase 08A daily-brief context builder, and the Phase 08D MCP resource surface (records 107–111).

---

## 1. Objective

Define and implement `DailyBriefHandoffPacketV1`: a single, stable, **metadata-only** packet shape that an
MCP client (Claude) renders as a human-readable executive brief. The packet adds **no retrieval logic** —
it is a read-only **projection** of the existing daily-brief assembly — and never carries raw content,
URLs, tokens, or final determinations.

## 2. Source reuse (no duplication)

`construction/second_brain/daily_brief/packet.py` calls `context._assemble_daily_brief(emit_receipt=False)`
**once** (the existing broker → research-packet → cards pipeline) and reshapes its already-redacted,
source-linked output. It does **not** call the broker or readers directly and does **not** touch MCP
dispatch — keeping Phase 08D isolation intact. Nothing is persisted (no packet receipt table was added;
the prompt makes receipts optional and the current pattern is preserved unchanged).

## 3. Packet shape

Top-level fields (19): `packet_id`, `packet_version`, `generated_utc`, `brief_date`, `project_scope`,
`mode`, `source_coverage_summary`, `what_matters_today`, `recent_changes`, `review_required_items`,
`aging_watchlist`, `meeting_prep`, `risk_watchlist`, `stale_or_low_confidence_warnings`,
`accepted_memory_context`, `suggested_follow_up_questions`, `source_refs`, `guardrails`,
`rendering_instructions`.

Each source-linked **item** (16 metadata-only fields): `item_id`, `section`, `priority`, `project_key`,
`title_redacted`, `summary_redacted`, `source_family`, `source_ref_hash`, `source_ref_label`,
`review_tier`, `review_required`, `confidence_class`, `freshness_label`, `stale_warning`, `allowed_use`,
`blocked_uses`. Source refs are emitted **hashed** (`source_ref_hash`, sha256[:48]) plus a safe
`source_ref_label` (`family:record_type`) — the raw ref is never emitted.

Section → family mapping (deterministic; an item may appear under more than one lens, mirroring the
brief): `review_required_items` = any review-required item; `meeting_prep` = `meeting_prep_brief_sections`;
`aging_watchlist` = `aging_exposure_report_items`; `risk_watchlist` = `project_risk_digest_items`;
`recent_changes` = `cross_source_relationships` + `project_issue_history_items`;
`accepted_memory_context` = `accepted_long_term_memory` (always `allowed_use=advisory_context_only`);
`stale_or_low_confidence_warnings` = any item with stale flags or low confidence.

## 4. Guardrails & rendering instructions

Every packet carries the exact required guardrails block — `advisory_only`, `source_linked`,
`metadata_only`, `no_raw`, `no_writeback`, `no_final_determinations`, `claude_rendering_only` (all true) —
and a `rendering_instructions` block telling Claude to render an executive brief, preserve warnings, not
infer beyond the packet, make no final determinations, include the source-coverage note and follow-up
questions, and **not ask for raw records**. A `_reject_final_determination` lexicon flags (never emits)
determination language. The full serialized packet is run through `_assert_no_raw` (fail-closed).

Contract: `resources/json/phase_09_daily_brief_handoff_packet_contract.json`, registered as
`daily_brief_handoff_packet_contract` in `PHASE_09_CONTRACT_FILES`.

## 5. CLI

`hb-assistant second-brain daily-brief packet --date YYYY-MM-DD [--project-key K] [--mode dry_run|apply] --json`
and `hb-assistant second-brain daily-brief packet-proof --json` — added to the existing
`second-brain daily-brief` Typer group (command mapping documented in the contract evidence).

## 6. Validation

`ruff`/`mypy` clean. `tests/test_phase_09_daily_brief_packet.py` (12 tests) green: contract validation,
metadata-only, review-flag preservation, stale/low-confidence preservation, source coverage,
advisory-only accepted memory, raw-shaped rejection, final-determination flagging, no-writeback (0
`daily_brief_runs` rows), exact guardrails block, proof artifacts, and fail-closed on missing contract.
The full daily-brief suite (118 tests) stays green. Pre-existing phase-08a/b/c/d schema-lifecycle and
gate-report failures are out of scope (they fail identically on clean `HEAD`).
