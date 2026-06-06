# Daily Brief Handoff Packet Contract — DailyBriefHandoffPacketV1

**Phase:** 09 Addendum — Daily Brief / MCP Handoff & Rendering · **Prompt:** 01
**Generated (UTC):** 2026-06-06T09:32:59.341369+00:00 · **repo_sha:** 0682b66dc68e201cb4547bbd91d50b7aba668182

## Purpose

A stable, **metadata-only** daily-brief packet that Claude can safely consume through MCP and render as a human-readable executive brief. The packet is a **read-only projection** of the existing daily-brief context (`build_daily_brief_context` / `_assemble_daily_brief`) — no retrieval logic is duplicated in MCP, nothing is persisted, and no raw content/URLs/tokens or final determinations are ever emitted.

## CLI

```bash
hb-assistant second-brain daily-brief packet --date YYYY-MM-DD --json
hb-assistant second-brain daily-brief packet-proof --json
```

Command mapping: implemented as `daily-brief packet` / `daily-brief packet-proof` under the existing `second-brain daily-brief` group.

## Required packet fields

- `packet_id`
- `packet_version`
- `generated_utc`
- `brief_date`
- `project_scope`
- `mode`
- `source_coverage_summary`
- `what_matters_today`
- `recent_changes`
- `review_required_items`
- `aging_watchlist`
- `meeting_prep`
- `risk_watchlist`
- `stale_or_low_confidence_warnings`
- `accepted_memory_context`
- `suggested_follow_up_questions`
- `source_refs`
- `guardrails`
- `rendering_instructions`

## Per-item shape (metadata-only)

- `item_id`
- `section`
- `priority`
- `project_key`
- `title_redacted`
- `summary_redacted`
- `source_family`
- `source_ref_hash`
- `source_ref_label`
- `review_tier`
- `review_required`
- `confidence_class`
- `freshness_label`
- `stale_warning`
- `allowed_use`
- `blocked_uses`

Source refs are emitted as **hashes** (`source_ref_hash`) plus a safe `source_ref_label` (family + record type) — never the raw ref.

## Guardrails block (carried in every packet)

```json
{
  "advisory_only": true,
  "source_linked": true,
  "metadata_only": true,
  "no_raw": true,
  "no_writeback": true,
  "no_final_determinations": true,
  "claude_rendering_only": true
}
```

## Rendering instructions (for Claude)

- Render as a human-readable executive brief.
- Preserve all warnings (stale, low-confidence, and review-required).
- Do not infer beyond the packet contents.
- Do not make final determinations (financial, legal, claim, payment, safety, schedule, contractual).
- Include the source coverage note.
- Include the suggested follow-up questions.
- Do not ask for raw records.

## Representative packet (from controlled, metadata-only inputs)

- packet_id: `dbp_2d348570c8e5cdc2398de1e1bf09902e` · brief_date: 2026-06-02 · project_scope: P1 · mode: dry_run
- source_coverage: 0.5 · source_ref_count: 6 · families_present: accepted_long_term_memory, aging_exposure_report_items, cross_source_relationships, project_issue_history_items, project_risk_digest_items
- what_matters_today bullets: 1
- section counts:
  - recent_changes: 3
  - review_required_items: 1
  - aging_watchlist: 1
  - meeting_prep: 0
  - risk_watchlist: 1
  - stale_or_low_confidence_warnings: 2
  - accepted_memory_context: 1

