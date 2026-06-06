# 180 — Daily Brief V2 Rendering Template Rewrite (Phase 09 Addendum, Prompt 03)

## Context

Prompts 01–02 built the V2 packet (`render_payload` / `governance_metadata` split + record-level
enrichment with the count-vs-detail rule). The Claude rendering template and rendered-output proof were
still the old V1 structure (What Matters Today / Review-Required / Aging / Meeting Prep / Risk / Source
Coverage / Follow-Up + Advisory Notice block) — exactly the governance-heavy, count-only output the
Prompt 00 baseline flagged. Prompt 03 rewrites the template to a concise executive structure and
rewrites the rendered-output proof to **fail** when internal proof/governance commentary appears.

## Design

### Executive structure
The rewritten templates instruct Claude to call `hb_daily_brief_packet`, render **only** the
`render_payload`, and produce exactly five sections + a one-line footer:

```
# Daily Brief — YYYY-MM-DD
## Yesterday            (bullets)
## Today               (Time | Meeting | Project | Prep / Related Items)
## Next 7 Days         (Date | Project | Item | Type | Responsible | Why It Matters)
## Needs Attention     (Priority | Project | Item | Reason | Recommended Focus)
## Focus               (3–5 numbered items)
---
_Source-linked advisory brief. Verify in source systems before final action._
```

Must-do: be brief/descriptive, use project names/keys, surface record-level detail, write
"detail unavailable" instead of a bare count, ≤5 focus items. Must-not-render (explicit prohibitions in
the prompt body): packet provenance/hash tables, guardrail matrix, source coverage as a body section,
source-family lists, relationship-count summaries, proof paths, generated utc, mode/dry-run commentary,
suggested follow-up questions, repeated disclaimers, raw json.

### MCP tool now serves V2
`mcp_daily_brief_packet_wrapper` (`mcp/wrappers.py`) now returns `build_daily_brief_packet_v2`, so the
tool delivers `render_payload` / `governance_metadata` end-to-end. `include_rendering_instructions=false`
drops `governance_metadata.rendering_instructions`. `daily_brief_handoff_proof.py` validates the tool
output against the **V2** contract: render carries the required sections, governance carries the
required metadata, no governance key leaks into render, `packet_version == DailyBriefHandoffPacketV2`,
and source refs (under governance) are hashed.

### Validators
- **Template proof** (`mcp/render_template_proof.py`): `_REQUIRED_SUBSTRINGS` rewritten to the new
  contract — calls the tool, renders `render_payload`, the five section headers, the one-line footer,
  "detail unavailable", the explicit "do not render" prohibitions, no determinations, storage policy.
- **Rendered-output proof** (`daily_brief/rendered_quality.py`): `validate_rendered_brief` is now
  structural + forbidden-content. It requires the five sections and FAILS on: packet provenance/hash
  table, guardrail matrix, source-coverage wall, more than one advisory disclaimer, a count-only
  schedule table without rows or a "detail unavailable" notice, JSON blobs, source-family lists, proof
  paths, generated utc, mode/dry-run, follow-up questions, final-determination language, source-system
  writeback claims, and raw-shaped values. The safe fixture `_SAMPLE_RENDERED_BRIEF` is the new
  executive structure; one tampered variant per failure mode proves each check is non-vacuous.

## Surfaces

- `resources/templates/claude_daily_brief_{scheduled_task,manual_run}.md`
- `src/hb_assistant/construction/second_brain/mcp/render_template_proof.py`
- `src/hb_assistant/construction/second_brain/daily_brief/rendered_quality.py`
- `src/hb_assistant/construction/second_brain/mcp/wrappers.py`
- `src/hb_assistant/construction/second_brain/mcp/daily_brief_handoff_proof.py`
- `tests/test_phase_09_daily_brief_rendered_quality.py`, `test_phase_09_claude_render_template.py`,
  `test_phase_09_mcp_daily_brief_handoff.py`
- Evidence under `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/`
  (template copies + proofs + the V2 tool doc).

## Guardrails

Read-only, metadata-only, advisory-only, no external writeback, no final determinations, fail-closed —
unchanged. One-line advisory footer only; ≤5 focus items; "detail unavailable" instead of bare counts.
No raw body/subject/email/URL/token/header in templates, fixture, or proof output. The
`mcp-handoff-status` `claude_rendering_template_status` and `rendered_brief_quality_status` fields run
these rewritten proofs unchanged.
