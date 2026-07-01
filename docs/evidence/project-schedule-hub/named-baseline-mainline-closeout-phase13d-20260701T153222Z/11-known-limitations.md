# Known limitations — Phase 13D

## P3 residuals (carry forward)

1. Named export headline may duplicate "compared against" phrasing.
2. Tropical driver `FILTER-OUT-50` shows `disposition_source: preview` until named Workbench sync for that activity.
3. Deterministic export fallback is a classified fallback, not a full narrative QA pass.

## P3 discovered in mainline verification (non-blocking)

4. `test_project_schedule_hub_api.py` PM-field identifier tests fail on substring `schedule_version_key` because Phase 13A+ provenance exposes `comparison_schedule_version_key` in hub comparison actions JSON. Fix: tighten test to match field names, not substrings.

## Resolved (Phase 13A–13C)

| Was | Status |
|-----|--------|
| Named export 422 on contract/secondary | Resolved — all bases 200 on mainline |
| prior-update-like named export body | Resolved — hub-context export |
| Driver Detail no disposition | Resolved — scoped lookup + UI |
| Workbench export missing `comparisonBasis` | Resolved |

No new P0/P1/P2 limitations identified.
