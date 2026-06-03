# 86 — Phase 08B: No-Writeback / No-Raw-HTML Proof (Prompt 14)

**Status:** Implemented (additive). Schema **V34 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `d7498f6` (08B Prompt 13; 08A closeout `954a518` is ancestor).
**Scope:** Extends the existing `build_second_brain_no_writeback_proof` with an explicit **no-raw-HTML**
facet. No schema change, no new table, no new CLI command — the `no-writeback-proof` surface gains a
check + a `no_raw_html_persisted` field.

## Context

The no-writeback proof (`construction/second_brain/safety.py`) scans second-brain module source +
live receipt rows + generated dry-run output for **secrets** (JWT/PEM/bearer/SAS/AWS) and **raw-leak**
patterns (URLs/emails/iCal), probes the `CHECK(col = 0)` guard columns, and checks model receipts are
metadata-only. The Prompt-10 HTML renderer made HTML a first-class artifact, and the guardrails forbid
"raw HTML in receipts" — but **no scan proved it**: none of the secret / raw-leak patterns match
`<!DOCTYPE html>` / `<html>` / `<script>` / `<style>` / `<div>`. So raw HTML in a receipt cell or
generated output would have slipped through. This prompt closes that gap.

## Design

- `_HTML_MARKUP_PATTERNS` + `_scan_text_for_html_markup(text) -> list[str]` — value-shaped, matches
  **actual tags**: `<!doctype`, and `<` (optionally `/`) followed by a known tag name (`html`, `head`,
  `body`, `script`, `style`, `link`, `iframe`, `svg`, `img`, `div`, `span`, `table`, `meta`,
  `section`, `article`, `aside`, `main`, `header`, `footer`, `canvas`, `object`, `embed`). It does NOT
  match a stray `<`, and crucially does NOT match the `.html` path substring legitimately stored in
  receipts (verified by test). Mirrors `_scan_text_for_secrets`.
- `_scan_second_brain_tables_for_html(conn)` — loops the `_PHASE_08A_TABLES` live string cells applying
  the markup scan (mirrors the existing content-leak loop; dedup key `f"{table}.{col}: {label}"`).
- `_scan_generated_outputs()` now returns `{"secrets": [...], "html": [...]}` — the in-memory dry-run
  brief/handoff blob is scanned for HTML too.
- `build_second_brain_no_writeback_proof` computes `html_ok = no table HTML findings AND no generated
  HTML findings`, folds `html_ok` into `proof_passed`, adds two `checks_detail` entries
  (`sqlite_html_markup_scan_08b_tables`, `generated_brief_handoff_html_scan`), a top-level
  `no_raw_html_persisted` field (+ `_scope`), and a `raw_html_persisted: False` guardrail.

**Scope boundary:** the scan covers persisted rows + generated runtime output. It intentionally does
**not** scan the renderer's **module source** (`daily_brief_html.py` legitimately contains HTML
templates) nor the rendered HTML **file** under `<app_support>/html/` (legitimately HTML, outside the
repo). The proof concerns what is *persisted in receipts / DB*, not the deliverable artifact.

## Guardrails

Read-only; fail-closed (any HTML finding → `proof_passed=false`). No schema change; additive; no
existing check weakened. Phase 08A guardrails preserved (phase-08a-gates 8/1/0/3; phase-08b-gates
15/0/0/1; schema 34 / 151 tables unchanged).

## Known limitations / next

- The markup scan is pattern-based over a fixed tag allow-list; novel/obscure tags outside the list
  are not matched (the list covers the document/structural/script/style/embed tags that matter for a
  "raw HTML persisted" leak). `automation_execution` stays the lone deferred 08B gate.
