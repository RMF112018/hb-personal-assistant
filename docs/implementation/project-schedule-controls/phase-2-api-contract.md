# Project Schedule Hub Phase 2 API Contract

Date: 2026-06-29

## Route Contracts

Viewer-readable, read-only routes:

- `GET /api/projects/{project_key}/schedule?as_of=YYYY-MM-DD`
- `GET /api/projects/{project_key}/schedule/drilldowns?type=&limit=&offset=&as_of=`
- `GET /api/projects/{project_key}/schedule/drilldowns/{drilldown_type}?limit=&offset=&as_of=`
- `GET /api/projects/{project_key}/schedule/drivers?type=&limit=&offset=&driver_activity_id=&as_of=`
- `GET /api/projects/{project_key}/schedule/drivers/{activity_id}/detail?comparison_basis=&as_of=`
- `GET /api/projects/{project_key}/schedule/review-items?review_status=&limit=&offset=&as_of=&comparison_basis=`
- `GET /api/projects/{project_key}/schedule/workbench?review_status=&limit=&offset=&as_of=&comparison_basis=`
- `GET /api/projects/{project_key}/schedule/export?format=&as_of=&variant=&scope=&include_persisted_review=`
- `GET /api/projects/{project_key}/schedule/baseline`
- `GET /api/projects/{project_key}/schedule/imports/{import_id}/status`

Operator/admin-gated mutating routes:

- `POST /api/projects/{project_key}/schedule/review-items?as_of=`
- `PATCH /api/projects/{project_key}/schedule/review-items/{review_item_id}`
- `PUT /api/projects/{project_key}/schedule/baseline`
- `POST /api/projects/{project_key}/schedule/import-preview`
- `POST /api/projects/{project_key}/schedule/import-commit`
- `POST /api/projects/{project_key}/schedule/imports/{import_id}/recompute-cpm`

## Drilldown Aliases

The path-based drilldown routes are read-only aliases for the consolidated query route. They delegate to the same canonical drilldown implementation and support the same `limit`, `offset`, and `as_of` query parameters.

Required aliases:

- `remaining_later`
- `worsened_float`
- `milestones_later`
- `negative_float`
- `critical_remaining`

## Workbench Read Contract

`GET /api/projects/{project_key}/schedule/workbench` is read-only. It returns the preview workbench payload from the same read path as `GET /schedule/review-items` and does not sync or create persisted review items.

Persisting or syncing review items remains limited to `POST /api/projects/{project_key}/schedule/review-items`, which requires `X-HB-UI-Role: operator` or `admin`.

## Machine Error Codes

Phase 2 schedule hub API errors use the existing FastAPI envelope:

```json
{"detail":"machine_error_code"}
```

Documented codes:

- `invalid_as_of_date`: `as_of` is not an ISO `YYYY-MM-DD` date.
- `drilldown_type_required`: consolidated drilldown route omitted the required `type` query value.
- `unsupported_drilldown_type`: requested drilldown type is not supported.
- `driver_type_required`: driver drilldown route omitted the required `type` query value.
- `driver_activity_id_required`: driver drilldown type requires `driver_activity_id`.
- `unsupported_driver_drilldown_type`: requested driver drilldown type is not supported.
- `unsupported_export_format`: export format is not supported; JSON export is intentionally unsupported in Phase 2.
- `invalid_ui_role`: `X-HB-UI-Role` is not one of `viewer`, `operator`, or `admin`.
- `operator_role_required`: caller attempted a mutation without `operator` or `admin` role.

## Evidence Finding Status

- Drilldown 401: current contract is viewer-readable with `X-HB-UI-Role: viewer`; path aliases are explicit read routes.
- Drivers 422: missing `type` now returns `400 driver_type_required`.
- Workbench 401: read-only workbench GET is viewer-readable and non-mutating.
- JSON export 400: JSON remains unsupported and returns `400 unsupported_export_format`.
- `as_of` mismatch: schedule summary route honors `as_of` and selects the latest eligible schedule/update on or before the requested date.
