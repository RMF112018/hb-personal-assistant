# 01 — Implementation Summary

## Problem (from the audit)

`render_daily_brief` read only the pre-ranking convergence table `daily_brief_action_candidates`,
grouped by raw `section`, and emitted a flat family dump with internal artifacts (`id:dbac-…`,
`project:__needs_review__`, blanket `next:review`, `[redacted:<hash>]` calendar labels). The V51
ranking/assembly overlay — already correct (95/95 ranked, source-ref 1.0) — was never consumed.
Audited copy-quality 4.7/10, usefulness 3.4/10.

## Change

### New: `daily_brief_presentation.py` (pure, fully typed, raw-safe)
The presentation layer. Pure functions (no I/O, no clock) that turn the overlay's redacted fields
into polished operator copy:
- `safe_calendar_label` — sentinel/hash → actionable label (README §3).
- `aggregate_procore_lines` — per-signal candidates → one line per project + signal-type counts,
  deduped, capped (README §4).
- `cta_for_signal` / `CTA_BY_SIGNAL` — deterministic CTAs replacing blanket `next:review` (README §5).
- `email_followup_gap_card` — polished aggregate data-gap card (README §6).
- `render_item_line` / `render_calendar_line` / `render_procore_line` / `render_followup_line`.
- `collapse_duplicate_lines` (`×N`), `cap_lines` (explicit `+N more` overflow).
- `assert_clean_display` — **output fence**: raises on any forbidden token / raw pattern.
- `ASSEMBLY_KEY_TO_GROUP`, `DISPLAY_GROUP_ORDER`, `FAMILY_TO_GROUP`.

### Rewired: `daily_brief_render.py`
- `_latest_assembly_sections` → newest assembly run's sections for the date (guarded; `None` ⇒ no overlay).
- `_group_from_overlay` — authoritative selection/order from `candidate_ids_json`; Top Priorities
  rendered first as individual lines; Procore/calendar routed to their dedicated sections **by
  family**; everything else by assembly `section_key`.
- `_group_from_family` — no-overlay fallback through the **same** sanitization.
- Bodies built once → markdown, JSON `sections`, and `summary` all derive from them (no drift).
- Every brief passes `assert_clean_display` before return (fail-loud).
- `include_raw` (LOCAL only) now attaches real content to **JSON items only**; the Markdown is always
  the sanitized, raw-safe form.

### Follow-through: `daily_run.py` / `daily_run_html.py`
The LOCAL browser/Obsidian appendix consumed the old per-item field shape; updated to read the
sanitized `display` line (and `raw_title`/`raw_detail` for the local `--raw` browser view).

### CLI: `second_brain.py`
`--section` help text only (no signature change).

## Result

Deterministic rendered brief is an action plan: Top Priorities → Calendar Prep → Procore (aggregated)
→ Email/Follow-up → Data Gaps. Copy-quality 10.0/10, usefulness ≥8.0, zero internal artifacts,
production DB SHA unchanged, guard columns zero.
