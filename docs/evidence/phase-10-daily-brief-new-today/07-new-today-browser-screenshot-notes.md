# 07 — Browser render notes (Phase 10 · 252)

`06-new-today-browser-sample.html` is a self-contained, inline-CSS, zero-network browser brief
generated from the synthetic fixture (`tests/_phase_10_new_today_seed.py`). Open it directly in a
browser. The whole document passes the fail-closed egress scan (`scan_daily_run_html`) — see
`11-raw-safety-scan.json`.

## What you see (top → bottom)

1. **`Today's Daily Brief`** (h1) — no status/success banner above it on success.
2. The subhead: *Summary of the top items for 2026-06-12 and prep through 2026-06-19*.
3. **New Today** — three attention-class cards, each a colored left border:
   - **Needs your attention** (red) — the unreviewed invoice + the contract-status email + the
     cost-impact RFI;
   - **Team follow-up / monitor** (amber) — the RFI response + the change order;
   - **Awareness only** (blue) — the upcoming meeting + the updated permit-set file.
   Each bullet is a complete business sentence (names, numbers, amounts, project display names).
4. A collapsed **`▸ Run details / diagnostics`** `<details>` element — closed by default. Expanding it
   reveals the legacy candidate sections (here a demo `Procore Financial / Project Signals` /
   `Email / Follow-up` card) and the run/schedule/status metadata, explicitly labelled "Diagnostic
   context only — not part of the action brief." This block also passes the raw-safety scan and shows
   no raw project keys (the legacy `project_label` now resolves display names).

## Verified structurally (no manual screenshot tooling required)

- `New Today` appears **before** `Run details / diagnostics` in the document order.
- The h1 is `Today's Daily Brief`; the demo `success` status banner is inside the collapsed block,
  never above New Today.
- All dynamic values are scrubbed + HTML-escaped via `_esc`; the document is egress-clean.
