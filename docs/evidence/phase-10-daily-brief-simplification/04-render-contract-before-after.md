# 04 — Render contract: before / after

## Shared model (unchanged from 252, confirmed)

Both surfaces consume `new_today_presentation.build_render_model`:
- Markdown: `render_markdown(model)`.
- Browser HTML: `render_daily_run_html(..., new_today=model)` → `_render_new_today_cards(model)`.

Content cannot diverge; only presentation (bullets vs. cards) differs.

## Above-the-fold warning driver

- **Before:** `build_render_model(nt_digest, status=<legacy top-level status>)` — synthesis-degraded
  runs warned above the fold even when New Today was useful.
- **After:** `build_render_model(nt_digest, status=<New Today product status>)` — the warning appears
  only for product-relevant New Today degradation.

## Required visible structure (verified live, brief 2026-06-12)

`docs/evidence/.../07-browser-html-sample.html` (synthetic, commit-safe) and the real `/tmp` run both
produce, in order:

```
<h1>Today's Daily Brief</h1>
<p class='sub'>Summary of the top items for 2026-06-12 and prep through 2026-06-19</p>
[ above-the-fold warning — only when product-degraded ]
<section class='new-today'>
   Needs your attention
   Team follow-up / monitor
   Awareness only
<details class='diag'>Run details / diagnostics …</details>
```

Real-run section-marker scan (all on one rendered line, in order):

```
<h1>Today's Daily Brief</h1>
<section class='new-today'>
Needs your attention
Team follow-up / monitor
Awareness only
<details class='diag'>
```

Above-the-fold forbidden-token hits on the real run: **NONE**. The legacy run/status banner
(`Local-agent family · advisory …`), the synthesis/MEI sections, and the date-policy block
(`friday_next_week` et al.) are all **below** `<details class='diag'>`. Egress scan
(`scan_daily_run_html`): clean (`[]`).

## Project aliasing / redaction (unchanged, confirmed)

Project display names render (never raw keys); `_safe()` / `scrub_raw_text()` / `assert_clean_display`
/ `scan_text_for_forbidden` enforce raw-safety on both surfaces.
