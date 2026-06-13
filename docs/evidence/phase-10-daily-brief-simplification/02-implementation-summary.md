# 02 — Implementation summary

Surgical change at the right boundary — status ownership — reusing the New Today render layer shipped
in 252. No legacy code deleted.

## New file

- `src/hb_assistant/construction/second_brain/local_ai/new_today_usefulness.py`
  - `evaluate_new_today_status(*, digest, rendered_total_items, projection_receipt=None,
    model_enrichment_status="not_requested") -> dict`.
  - Pure (no store/IO/wall-clock). Returns `status` (`success|degraded`), `operator_usable`,
    `degraded_reasons` (stable codes), `visible_warning`, `model_enrichment_status`,
    `deterministic_fallback_used`.
  - Degradation is **product-relevant only**: `email_followup_degraded`, `projection_degraded`,
    `projection_coverage_degraded`, `all_events_dropped_raw_safety`. Synthesis/MEI are not inputs and
    cannot flip it (locked by `test_gate_cannot_see_legacy_synthesis_state`).

## Modified

- `src/hb_assistant/construction/second_brain/local_ai/daily_run.py`
  - New Today block (was lines ~672–707): two-pass — build the render model once to learn the
    post-fence item count, derive the New Today product status, then rebuild the model with that
    status so the above-the-fold warning is **New-Today-driven** (the one-line root-cause fix:
    `build_render_model(nt_digest, status=nt_status["status"])` instead of the legacy `status`).
  - Assembles the additive `daily_brief` block (primary_surface, status, operator_usable,
    degraded_reasons, `new_today{...}`, `diagnostics{...}` with legacy synthesis/MEI demoted to
    `diagnostic_only`). Added to the run return payload and to the status JSON.
  - `_write_status()` gained a `daily_brief` parameter; payload now carries `"daily_brief"`.
  - Top-level `status` and all existing fields left untouched (backward compat).

## Tests

- `tests/test_phase_10_daily_brief_simplified.py` — 14 tests: pure gate semantics, the crux (legacy
  synthesis degraded ≠ product degraded / no visible warning), empty-clean vs empty-degraded, email
  degraded, enrichment-field disambiguation, Markdown↔HTML parity, forbidden-token absence, full-run
  `daily_brief` block emission + status JSON, browser HTML structural order, guard columns zero.

## Docs

- `docs/architecture/253-daily-brief-simplified-generation-contract.md` (new).
- This evidence bundle.

## What was NOT touched

Source ingestion, projection layers, `new_today_digest`, the shared `build_render_model` /
`render_markdown` / `render_daily_run_html` content path, and all legacy candidate/ranking/assembly/
synthesis/MEI code — preserved as diagnostics.
