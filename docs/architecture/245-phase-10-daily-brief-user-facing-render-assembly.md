# 245 — Phase 10: Daily-Brief User-Facing Render / Assembly Presentation Layer

## Context

The daily-brief usefulness audit
(`docs/evidence/phase-10-daily-brief-output-usefulness-audit/`) proved the brief was not fit for
direct consumption (copy-quality 4.7/10, usefulness 3.4/10) even though the V51 ranking/assembly
engine was sound (95/95 ranked, source-ref 1.0, guard-clean). Root cause: `render_daily_brief` read
only the pre-ranking `daily_brief_action_candidates` table, grouped by raw `section`, and emitted a
flat family dump with internal artifacts (`id:dbac-…`, `project:__needs_review__`, `next:review`,
`[redacted:<hash>]` calendar labels). The assembly overlay was never consumed.

## Design

A pure presentation layer plus a render rewire — no schema change, no engine change, no new model
autonomy.

### `daily_brief_presentation.py` (pure, deterministic, raw-safe)

Stateless functions that map the overlay's already-redacted fields to operator copy:

- **Calendar safe labels** — sentinel/hash project keys → actionable labels
  (`__needs_review__` → "Calendar item needing project review", `__internal_*` → "Internal calendar
  block", real key → "Project meeting — <project>"). `[redacted:<hash>]` is never a label.
- **Procore aggregation** — per-signal candidates → one line per project + signal-type counts,
  deduped and capped.
- **CTA map** — deterministic CTA per Procore signal type / family, replacing blanket `next:review`.
- **Email/follow-up data-gap card** — aggregate count only when no follow-ups are eligible.
- **Output fence** — `assert_clean_display` raises on any forbidden token (`id:`, `dbac-`,
  `__needs_review__`, `__internal_`, `[redacted:`, `next:review`, table/column names) or raw pattern
  (emails, URLs, tokens, PEMs, tracebacks). The render runs it over the final Markdown before return.

### `daily_brief_render.py` (overlay consumption)

- Loads the newest assembly run's sections for the date; `None` ⇒ fall back to family grouping
  through the **same** sanitization.
- Section membership and order are authoritative from `daily_brief_assembly_sections.candidate_ids_json`
  (includes the top-N override); ranked rows supply rank/score only.
- Top Priorities render first as individual deduped lines. Remaining items route to dedicated display
  sections **by family** — Procore (aggregated), Calendar Prep (safe labels, capped with an explicit
  `+N more` overflow) — and otherwise by assembly `section_key`.
- Bodies are built once; Markdown, JSON `sections`, and `summary` counts all derive from them.

### Display order (README contract)

Top Priorities → Needs Review / Decisions → Calendar Prep → Procore Financial / Project Signals →
Email / Follow-up → Data Gaps / Degraded.

## Guardrails

- Read-only, deterministic, no writeback; model layer optional and advisory (`--no-client` is a valid
  authoritative path).
- User-facing Markdown is always sanitized. `--raw` (LOCAL only) attaches real content to JSON items
  and the local browser HTML for inspection — never to the committed/user-facing Markdown.
- Production DB never mutated; all sample generation runs against a `/tmp` copy via `--db`.

## Browser-consumer parity (251 v2)

The scheduled/browser consumer (`daily_run` → `daily_run_html.render_daily_run_html`) must share the
same sanitized contract as the Markdown path. `_render_section_cards` renders each section's
`render_daily_brief(...)["sections"][].lines` — the exact raw-free, aggregated lines produced by the
presentation layer — and never reconstructs cards from raw per-candidate rows or emits candidate ids.
`items` is consumed only for an explicitly-gated LOCAL `--raw` detail block, scrubbed through `_esc`
(URLs/emails/tokens/join-links → safe markers) and labelled local-only; the no-raw browser path is
the merge gate. Status JSON remains redacted/raw-safe but is not subject to the strict user-facing
denylist (diagnostic metric keys like `source_ref_coverage` are allowed).

## Evidence

`docs/evidence/phase-10-daily-brief-user-facing-render-assembly/` — copy-quality 10.0/10,
usefulness 8.5/10, raw-safety pass, prod-DB SHA unchanged, guard columns zero. Browser-consumer fix
(251 v2): `16-browser-consumer-fix.md`, `17-daily-run-browser-scan.json` (scan pass),
`18-prod-db-sha-unchanged-v2.txt`.
