# Driver Detail disposition audit — Phase 13C

## Route

`GET /api/projects/{project_key}/schedule/drivers/detail?activity_id=&comparison_basis=&as_of=`

Use query form for activity IDs containing `/`.

## Before (13B)

- Driver detail returned movement/side-by-side only.
- No disposition fields; controls/workbench had scoped review items but driver detail did not surface them.

## After (13C)

### Backend (`build_driver_detail`)

**Prior update scope:** `get_review_item_for_version_scope(project, schedule_version, stable_key, activity_id)`

**Named baseline scope:** `NamedBaselineReviewIdentity` with full Phase 13 identity:
- project_key
- current schedule version
- review_scope (`named_baseline`)
- comparison_basis / slot
- baseline schedule version key
- source stable/activity key
- source metric + signal

Lookup via `get_by_identity` — **not** stable-key-only.

Response fields: `review_status`, `review_item_id`, `disposition_schedule_version_key`, `disposition_basis`, `disposition_source`, `review_scope`.

### Frontend (`ProjectScheduleDriverDetailPage`)

- **Review Disposition** card with status badge + humanized `dispositionSourceLabel()`.
- Raw `psri-*` / `psnbri-*` IDs only under collapsed **Technical activity reference** (`<details>`).

## Test coverage

- `tests/test_project_schedule_named_baseline_dispositions.py` — driver detail disposition for prior_update and named; slot isolation; no bleed.
- `ProjectScheduleDriverDetailPage.test.tsx` — disposition card visible; no primary raw ID copy.
- Tropical read-only: `13c-api-proof-driver-detail.json`.
- Browser: shot `07-driver-detail-disposition.png` — `Review Disposition` heading gate + no raw ID in card.
