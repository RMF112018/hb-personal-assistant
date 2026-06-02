# 73 — Phase 08B: Durable Delivery-Handoff Recovery + Render-View Contract

**Phase:** 08B (Automation Delivery & Observability) — Prompt 01 (gap preflight remediation)
**Schema:** V27 (additive; V1–V26 untouched)
**Status:** Implemented. Local-first, read-only against external systems; no external delivery,
no HTML rendering, no raw-content persistence.

## Problem

Two Phase 08A gaps blocked 08B build work (confirmed in the Prompt 00 rebaseline,
`docs/evidence/construction-intelligence-phase-08b-automation-hardening/00-repo-truth-rebaseline.md`):

1. **Handoff was not durable.** `run_daily_brief()` builds a `DeliveryHandoffPayload`
   (sections → `HandoffLine`, notification summary, HTML render-data) **in memory only**. On
   `--emit-receipt` it persisted counts (`daily_brief_runs`) + flat refs (`daily_brief_source_refs`)
   but **not** the structured sections. The only reader returned counts. A launchd-driven 08B
   pipeline that generates in one process and delivers/renders in another could not recover the
   handoff after process exit.
2. **No render contract.** Nothing produced a deterministic, render-ready view a future HTML
   renderer could consume; the existing markdown renderer reads context cards, not the handoff.

## Design

### V27 table — `daily_brief_handoff_lines`

One additive table (FK → `daily_brief_runs(brief_run_id) ON DELETE CASCADE`) storing, per line:
`section`, `line_index`, `title_redacted`, `review_tier`, and `source_refs_json` (safe
`{source_family, source_ref, …}` pairs only). It carries the same nine no-raw / no-writeback
`CHECK(col = 0)` guard columns as `daily_brief_runs`. Combined with the existing `daily_brief_runs`
(counts/status/tier) and `daily_brief_source_refs`, this is sufficient to reconstruct the full
handoff. The notification summary and HTML render-data are **derived**, not stored, so no
redundant tables are added.

`src/hb_assistant/store/migrator.py`: `LATEST_SCHEMA_VERSION = 27`; `V27_STATEMENTS` + a V27
apply block mirroring the V26 pattern (idempotent `CREATE TABLE IF NOT EXISTS` + index;
`schema_migrations` row inserted once). The lifecycle contract gains a `daily_brief_handoff_lines`
entry (`phase_owner: 08B`, `v: V27`, `operational_empty_expected`) and `table_count 141 → 142`.

### Persistence wiring

`write_daily_brief_handoff_lines(sections, *, brief_run_id, db_path)` is a **sibling** writer in
`daily_brief/store.py` (the existing `write_daily_brief_run` column tuple is unchanged, preserving
the 08A agent proof). It is called from the **same `emit_receipt` path** in `run_daily_brief`, so
durable persistence rides the existing dry-run-default posture (nothing is written without
`--emit-receipt`). Each line's `source_refs` is run through `_reject_forbidden_refs` before
`json.dumps`.

### Reconstruction

`read_daily_brief_handoff(brief_run_id, *, db_path) -> DeliveryHandoffPayload | None` rebuilds the
payload from `daily_brief_runs` + `daily_brief_handoff_lines` + `daily_brief_source_refs`. Sections
are pre-seeded with all canonical `HANDOFF_SECTIONS` keys and filled in `(section, line_index)`
order so the reconstructed shape mirrors the in-memory handoff exactly; the notification summary
and `HtmlRenderingData` (`rendered=False`) are derived. Returns `None` for an unknown run id.

### Render-view contract

`daily_brief/render_view.py::build_daily_brief_render_view(handoff, *, context_quality_class,
generated_utc)` is a **pure, deterministic** builder (no DB/model/IO) returning a new
`DailyBriefRenderView` (`extra="forbid"`, `rendered=False` enforced by validator). Sections follow
canonical order; lines carry redacted title, tier, and safe refs. This is the stable contract the
future HTML renderer consumes — **no HTML is emitted here.**

### CLI

`second-brain daily-brief render-view [--date | --run-id] [--json]` is **read-only**: it
reconstructs a persisted handoff and emits the deterministic render view (exit 2 on missing
selector, exit 4 when the run is not found). No apply, no emit, no HTML.

### Safety

`daily_brief_handoff_lines` is added to `safety._PHASE_08A_TABLES`, so the no-writeback proof's
guard-probe + persisted-content leak scan covers it (the proof now scans nineteen second-brain
tables and 52 modules; `proof_passed=true` at schema 27).

## Guarantees / invariants

- No external delivery, no HTML rendered, no raw content (DB `CHECK(=0)` guards + model validators
  + `_reject_forbidden_refs` + the no-writeback content-leak scan).
- Apply-capable commands remain dry-run by default; `render-view` is read-only.
- Reconstruction is deterministic and metadata-only; all runtime artifacts stay outside the repo.

## Known limitations

- Top-level aggregate `handoff.source_refs` reconstruct to their durable `{source_family,
  source_ref}` identity (+ `evidence_trail_id`/`confidence_class` when persisted). The
  `record_type`/`review_tier` annotations some in-memory refs carry are **not** in the V26
  `daily_brief_source_refs` schema and are not reconstructed — a pre-existing V26 limitation. The
  **per-line** `source_refs` (the new V27 table) round-trip verbatim, and the **sections** — the
  data previously lost — round-trip exactly.
- HTML rendering and notification delivery remain deferred to later 08B work
  (`automation_hardening` gate). This prompt ships the contract, not the renderer.
