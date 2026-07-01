# Known limitations — Phase 13C

| ID | Area | Severity | Status | Notes |
|----|------|----------|--------|-------|
| L1 | Export narrative | P3 | Open | Named export headline/synopsis may duplicate "compared against" phrasing; content is correct. |
| L2 | Driver disposition | P3 | Open | Tropical `FILTER-OUT-50` shows `disposition_source: preview` until operator syncs named workbench for that activity. |
| L3 | Deterministic fallback | P3 | Documented | `export_mode: deterministic_fallback` used when narrative QA fails; full QA pass still preferred for PM memos. |
| L4 | Legacy `baseline` basis | P3 | Unchanged | Legacy single-baseline selection path not in Tropical named-slot proof matrix. |

## Resolved in 13C (was 13B)

| Was | Resolution |
|-----|------------|
| P1 — Named export 422 on contract/secondary | Named export from hub context; Tropical all bases 200 |
| P1 — prior-update-like named export body | Full named summary rebuild |
| P2 — Driver Detail no disposition | Scoped lookup + UI card |
| P2 — Workbench export missing `comparisonBasis` | Fixed + tested |
