# 82 — Phase 08B: Local HTML Brief Renderer (Prompt 10)

**Status:** Implemented (additive). Schema **V31 → V32** (one new table); package stays `1.3.0`.
**Baseline:** atop `cea914b` (08B Prompt 09; 08A closeout `954a518` is ancestor).
**Scope:** A dry-run-by-default renderer that produces a polished, **fully self-contained** interactive
HTML daily brief, written outside the repo, plus a V32 render-receipt ledger and a proof-backed
`daily_brief_html_render` gate. `automation_execution` stays the only deferred 08B gate.

## Context

The durable delivery handoff (`HtmlRenderingData` in `daily_brief/models.py`) has always been
*structured render-data for a **future** HTML renderer* (`rendered=False`, validator rejects
`rendered=True`); **no HTML was emitted anywhere in the repo**. This prompt builds that renderer as a
new, explicitly-bounded surface — it does **not** touch the existing structured-only render-data /
render-view guardrails (`no_html_rendered` / `no_html_rendering` stay true for those surfaces).

## Design

New module `construction/second_brain/daily_brief_html.py` (same P09 agent shape; injects
`db_path`/`now`/`html_dir`; reuses `read_daily_brief_handoff`, `read_latest_daily_brief_runs`, and
`daily_brief/output.py::_atomic_write_text`):

- `render_daily_brief_html(payload, *, generated_label)` — pure, deterministic, fully self-contained
  HTML from `DeliveryHandoffPayload`. Inline `<style>` + inline `<script>` (no `src`/`url(`/`http`)
  implement: **project + tier filter** chips (toggle `data-project`/`data-tier` visibility),
  **collapsible sections**, a slide-out **evidence drawer** (per-line `source_refs`), a **warning
  banner** (degraded/blocked), a **meeting timeline** (`meeting_prep`), a **mandatory-review panel**
  (`file_review_queue`), and **print CSS** (`@media print`). All text `html.escape`d; the project
  dimension is parsed from `project_signals` titles (cross-project items bucket to "General").
- `_scan_html_for_external_assets(html)` — value-shaped scanner for `http(s)://`, protocol-relative
  refs, `<link>`/`<script src>`/`<img src>`/`<iframe>`, `@import`, `url(//…)`, `fetch(`,
  `XMLHttpRequest`, `WebSocket`, `.sendBeacon`, dynamic `import(`.
- `evaluate_daily_brief_html_render` (read-only) → `HTML_RENDER_NEVER_GENERATED` / `_BLOCKED` /
  `_STALE` / `_ALREADY_RENDERED` / `_ELIGIBLE` over V26 runs + V32 receipts.
- `run_daily_brief_html_render_agent(mode=…, html_dir=…, emit_receipt=…)`: **dry-run default**
  previews + writes nothing; **apply** (only when eligible) renders → runs the fail-closed scan
  (refuse on any hit → `HTML_RENDER_EXTERNAL_ASSET_BLOCKED`) → writes the `.html` to
  `html_dir or PathPolicy().get_html_dir()` (`<app_support>/html/`) → records a V32 receipt. The
  optional V28 agent receipt (`agent_id='daily_brief_html_render_agent'`) is emit-gated.
- `build_daily_brief_html_render_proof()` drives the gate across never-generated / blocked / stale /
  eligible (dry-run) / completed (apply) / already-rendered, asserting dry-run writes nothing, the
  HTML carries the required UI markers, `no_external_assets`, and a values-only no-raw scan.

### Schema (V32) / safety / path / gate / policy / CLI

- `migrator.py`: `LATEST_SCHEMA_VERSION 31 → 32`; new `daily_brief_html_render_receipts` — metadata
  only (redacted app-support path + content/path hashes), **`CHECK(no_external_assets = 1)`** fail-
  closed positive invariant, `mode IN ('dry_run','apply')`, FK to `daily_brief_runs`, the 9 standard
  `CHECK(col = 0)` guards. Raw HTML is never stored. Registered in `safety._PHASE_08A_TABLES` (the
  `=1` CHECK is safely ignored by the `CHECK\((\w+)=0\)` guard regex; the 9 `=0` guards still derive).
- `path_policy.py`: lazy `get_html_dir()` → `<app_support>/html` (modeled on `get_locks_dir`).
- `data_quality.py`: new `daily_brief_html_render` proof-gate → **pass**; phase-08b-gates → **13 pass
  / 0 warning / 0 fail / 1 deferred**.
- Policy seed + both contracts updated with the seven `HTML_RENDER_*` reason codes + the gate;
  lifecycle `table_count 148 → 149` + the new table entry (`v: V32`).
- CLI: `second-brain automation html-status` (read-only) + `render-html` (apply-capable, **dry-run
  default**, `--brief-date`, `--emit-receipt` off by default; exit 0/3/2).

## Guardrails

Self-contained: inline CSS/JS only; the fail-closed scan refuses to write any HTML with an external
asset/network reference, and the V32 row only persists with `no_external_assets = 1`. No raw HTML in
SQLite (only path/content hashes); the page is rendered from the structured, escaped handoff, never a
model response. No external writeback/delivery. The `.html` lives at `<app_support>/html/` — outside
the repo and the vault. Dry-run is the default; the V28 receipt is emit-gated. Phase 08A guardrails
preserved (phase-08a-gates 8/1/0/3; no-writeback proof passes at schema 32).

## Known limitations / next

- `automation_execution` stays deferred — the final executor + morning-orchestrator wiring (the
  renderer is ready to be wired as an optional render step).
- The project filter derives projects from `project_signals` titles (handoff lines carry no explicit
  project key); cross-project items bucket to "General". Tier filtering is exact (`review_tier`).
- Apply writes the V32 receipt unconditionally (the render ledger); the V28 receipt is emit-gated.
  Idempotency keys on a prior `rendered` receipt for the brief run/date.
