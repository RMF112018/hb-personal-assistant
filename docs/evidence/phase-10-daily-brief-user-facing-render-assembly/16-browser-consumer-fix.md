# 16 — Daily-Run Browser Consumer Fix (251 v2)

## Problem (pre-merge proof)

v1 fixed the direct `daily-brief render` Markdown path, but the isolated scheduled/browser consumer
(`daily-run run --no-synthesize --no-model-enriched-intelligence --no-raw`) still failed the
user-facing scan. The browser HTML renderer `_render_section_cards`
(`local_ai/daily_run_html.py`) rebuilt the brief body from raw per-candidate rows (`sec["items"]`)
and appended an internal candidate id:

```html
<div class='ttl'>Financially material: invoice_payment_due</div>
<div class='cid'>id: dbac-066c9284c0e64...</div>
```

Result: ~45–50 individual Procore cards (no aggregation), `id: dbac-…` leaks, and
`Email / Follow-up: None.` / `Data Gaps / Degraded: None.` (the gap/degraded content lives in the
render payload's `lines`, which the browser ignored).

## Fix

`_render_section_cards` now renders the **same sanitized presentation contract** as the Markdown
path — the render payload's `sec["lines"]` (produced by `daily_brief_presentation`) — never the raw
`items`, and never a candidate id. `items` is used only for an explicitly-gated LOCAL `--raw` detail
block (scrubbed through `_esc`, labelled local-only, no ids/refs).

After (browser HTML, `--no-raw`):

```html
<h2>Procore Financial / Project Signals<span class='count'>2</span></h2>
<div class='item'><div class='ttl'>tropical — 18 payment-due invoice signals, 10 approved-not-paid invoice signals, 6 negative budget variance signals, 5 unpaid commitment change-order signals. Review payment status and confirm next payment action.</div></div>
<div class='item'><div class='ttl'>alton-hilltop-pbg — 1 RFI cost-impact signal. Confirm pricing exposure and response owner.</div></div>
```

```html
<h2>Email / Follow-up ...</h2>
<div class='item'><div class='ttl'>Email follow-up unavailable — 281 email thread summaries exist, but none are eligible for follow-up watch. Review the email follow-up projection/watch eligibility inputs.</div></div>
<h2>Data Gaps / Degraded ...</h2>
<div class='item'><div class='ttl'>Advisory model layer unavailable; deterministic ranking is authoritative for this brief. No action needed — the priorities above are complete.</div></div>
```

## True-pipeline validation (on a /tmp copy of PLAIN prod)

- procore-digest 50 / calendar-prep 45 / follow-up-watch 0 / synthesize 0 / rank 95-of-95
  (coverage 1.0, usefulness 0.9, guard_clean) — engine unchanged.
- Direct Markdown render: unchanged, still passes.
- Isolated `daily-run run --apply --no-raw --no-synthesize --no-model-enriched-intelligence
  --no-open-browser`: status `success`, egress scan clean, 4 browser HTML files written, vault note
  not written (no `--confirm-vault-write`).
- Browser HTML: all 5 sections present (`Top Priorities`, `Calendar Prep`, `Procore Financial /
  Project Signals`, `Email / Follow-up`, `Data Gaps / Degraded`); Procore aggregated to 2 lines (not
  ~50); zero `class='cid'` / `id:` / `dbac-` / sentinels / `[redacted:` / `next:review` / table
  names / `None.`.
- User-facing scan over `browser-apply` + `vault-apply`: **status pass**, 0 findings
  (`17-daily-run-browser-scan.json`).
- Production DB SHA unchanged (`18-prod-db-sha-unchanged-v2.txt`).

## Scope

One source change (`daily_run_html.py::_render_section_cards` + the audit-appendix count key) plus a
browser HTML test. No schema, no engine, no Markdown behavior change. The `--raw` browser feature is
preserved (gated, scrubbed, id-free).
