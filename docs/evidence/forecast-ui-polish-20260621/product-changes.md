# Forecast UI polish — product changes (2026-06-21)

## Visual / UX improvements

1. **Forecast command center** (`/forecasting`) — summary grid (storage, packages, latest forecast, review signals, external evals, config snapshot), subnav, primary CTAs (Generate, Review latest, Evaluate, View configuration).
2. **Storage & database readiness** (`/forecasting/runtime`) — checklist status panel, “Managed by HB” posture, repair action, collapsed admin-only advanced path override.
3. **Run center** (`/forecasting/runs`) — clearer generate workflow copy, generation history, live-config generation with type selector.
4. **Package detail** — headline metrics, validation, cost rows, review queue, monthly/probability/risk sections with `displayValue` redaction-safe rendering.
5. **External evaluation** — guided steps (upload → map → results), operator-facing labels.
6. **Configuration viewer** — domain tabs via derived selection, construction-facing empty states.
7. **Config proposals** — safer proposal copy, promotion gating unchanged, friendly proposal labels.
8. **Shared chrome** — `ForecastPageChrome`, `ForecastStatusPill`, consistent status taxonomy (Ready / Needs attention / App-managed / Advisory).

## Copy changes (representative)

| Before (technical) | After (construction-facing) |
|--------------------|----------------------------|
| Data sources / runtime configuration | Local forecast storage / Storage & database readiness |
| Validated | Ready |
| Upload an external forecast | Upload operator forecast |
| Propose a configuration edit (section) | Configuration proposals |
| Human-review queue | Review queue |
| Generate from live config (button) | Generate |

Admin/advanced panels retain explicit path terminology only when expanded.

## Guardrails preserved

- End users not asked for absolute paths during normal setup
- App-managed storage presented as default (“Managed by HB”)
- Manual path overrides: admin-only, collapsed, labeled advanced
- Advisory-only surfaces; no writeback language introduced
- Backend role gates and redaction tests unchanged
- No weakening of runtime validation or redaction tests