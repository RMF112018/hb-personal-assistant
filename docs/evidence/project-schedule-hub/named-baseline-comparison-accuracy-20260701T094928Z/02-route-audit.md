# Route audit — named baseline comparison_basis threading

**Scope:** Phase 13A fix + Phase 13B evidence capture (`as_of=2026-07-03`, project `tropical`).

## API routes (`src/hb_assistant/construction/analytics/api.py`)

| Route | `comparison_basis` param | Named-baseline behavior |
|-------|--------------------------|-------------------------|
| `GET …/schedule/baselines` | n/a | Returns named slot selections + available versions |
| `GET …/schedule/controls` | yes (default `prior_update`) | Resolves slot via `validate_controls_comparison_basis`; returns `baseline_context`, `provenance.comparison_label`, `sections.movement` |
| `GET …/schedule/review-items` | yes | Workbench preview scoped to basis; named items use `psnbri-*` |
| `GET …/schedule/drivers/detail` | yes (`activity_id` query) | Returns `baseline_context` for named slots |
| `GET …/schedule/drilldowns` | yes + `type` | Named drilldown includes `comparison_schedule_version_key`, `source_model: named_slot` |
| `GET …/schedule/drivers` | yes + `type` | Driver list drilldown honors basis |
| `GET …/schedule/export` | yes + `format` | Attempts basis-specific memo; may 422 on QA gate |

## Frontend pass-through

| Surface | File | Basis propagation |
|---------|------|-------------------|
| Schedule Hub | `frontend/src/pages/ProjectSchedulePage.tsx` | Comparison basis selector; passes `comparisonBasis` to drilldown/export |
| Workbench | `frontend/src/pages/ProjectScheduleWorkbenchPage.tsx` | `comparison_basis` query param drives filter + cues |
| Driver Detail | `frontend/src/pages/ProjectScheduleDriverDetailPage.tsx` | `comparison_basis` + `activity_id` query params |
| API client | `frontend/src/lib/api.ts` | `comparisonBasis` on export, drilldown helpers |

## Evidence artifacts

- Consolidated controls: `06-api-proof-controls.json`
- Workbench GET (read-only): `07-api-proof-workbench.json`
- Driver detail: `08-api-proof-driver-detail.json` (`FILTER-OUT-50`, query route)
- Drilldown/export: `13b-api-proof-drilldowns.json`, `13b-api-proof-export.json`
