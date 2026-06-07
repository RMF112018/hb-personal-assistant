# 05 Route and API Alignment Audit

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


## Summary

Backend route inventory is broad and intentionally guarded. The main alignment gaps are not missing backend core surfaces, but mismatch between frontend assumptions and backend response shapes.

## Highest-Risk Alignments

| Area | Frontend expectation | Backend truth | Impact |
|---|---|---|---|
| Project subpages | `items` array or raw array | object envelope with `metric_cards`, `attention_items`, `sections` | TypeError risk on `.slice()` |
| My Items | five section endpoints | only `/api/my-items` | 404s / noisy failed queries |
| Projects portfolio | `projects` or `items` array | `project_keys`, `metric_cards`, `attention_items` | individual projects may not render |
| Today Important | `/api/today/important` exported | no backend route | unused dead API export / future 404 |
| Admin page | success data assumed | 403 for non-admin | confusing “Loading” UX |

See `frontend_route_inventory.json` and `frontend_api_call_inventory.json` for full details.
