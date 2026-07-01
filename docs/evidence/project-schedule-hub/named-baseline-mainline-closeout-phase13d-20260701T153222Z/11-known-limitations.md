# Known limitations — Phase 13D

## P3 residuals (carry forward)

1. Named export headline may duplicate "compared against" phrasing.
2. Tropical driver `FILTER-OUT-50` shows `disposition_source: preview` until named Workbench sync for that activity.
3. Deterministic export fallback is a classified fallback, not a full narrative QA pass.

## Resolved in mainline verification

4. Hub API PM-field test drift — corrected with path-aware provenance key allowlist (`02c-backend-test-correction.md`).

## Resolved (Phase 13A–13C)

| Was | Status |
|-----|--------|
| Named export 422 on contract/secondary | Resolved — all bases 200 on mainline |
| prior-update-like named export body | Resolved — hub-context export |
| Driver Detail no disposition | Resolved — scoped lookup + UI |
| Workbench export missing `comparisonBasis` | Resolved |

No new P0/P1/P2 limitations identified.
