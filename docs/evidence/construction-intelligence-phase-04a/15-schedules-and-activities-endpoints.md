# Phase 04A — Add `schedules` + `activities` Endpoints (v2.0 company-scoped)

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)

Two new canonical endpoints, `schedules` and `activities`, are added to the Phase 04A registry. Both are Procore v2.0 company-scoped paths (the first Phase 04A endpoints to require `{company_id}` placeholder substitution) and both wrap their response in a `{"data": [...]}` envelope (the first Phase 04A endpoints to use this envelope style). The orchestrator's `_resolve_path` is extended to substitute `{company_id}` from the existing `COMPANY_ID = "5280"` constant; the shared `http_client.paginate` body unwrap is extended to accept both `items` and `data` envelopes.

`activities` is the per-schedule child of `schedules`: when operator runs `--endpoint activities`, the orchestrator first fetches the schedules list (one HTTP call), then issues one activities GET per schedule (N+1), with each activity row carrying `parent_procore_id = schedule_id`. Mirrors the meeting-detail dispatch pattern.

## Outcome summary

| Metric                       | Value                                                                            |
| ---                          | ---                                                                              |
| Endpoints added              | `schedules`, `activities` (registry rows #19 and #20)                            |
| Schedules path               | `/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules`              |
| Activities path              | `/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules/{schedule_id}/activities` |
| Response envelope            | `{"data": [...]}` (first Phase 04A endpoints using this style)                   |
| Schedules smoke              | `980e7fb0` (1 record, 1 HTTP call)                                               |
| Activities smoke             | `6956f007` (10 records, 4 HTTP calls — 1 list + 3 paginated activities)          |
| Schedules apply              | `3afaca38` then `e15a76b4` (1 row, idempotent)                                   |
| Activities apply             | `7a46294e` then `3d45f0c1` (5 rows persisted with parent_procore_id, idempotent) |
| Verified set                 | 18 → **20**                                                                     |

## Schema attribution

Operator-supplied snippets (paraphrased):

**Schedules** — `GET /rest/v2.0/companies/{c}/projects/{p}/schedules` returns `{"data": [{schedule_id, project_id, company_id, schedule_name, schedule_type, is_active, data_date, start_date, calendar_id, parent_schedule_id, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by}]}`.

**Activities** — `GET /rest/v2.0/companies/{c}/projects/{p}/schedules/{s}/activities` returns `{"data": [{activity_id, activity_name, start_date, finish_date, duration, duration_unit, percent_complete, parent_id, ordered_parent_index, constraint_type, constraint_date, assigned_company, crew_size, calendar_id, deadline_date, deadline_variance, category_data, resource_data, is_critical, is_actual_start, is_actual_finish, total_float, notes, schedule_id, project_id, company_id, created_at, created_by, updated_at, updated_by}]}`.

## Infrastructure deltas

### `src/hb_assistant/procore/http_client.py`

Extended the `paginate.fetch` closure to accept both `items` (v1.x) and `data` (v2.0) wrappers:

```python
raw_items = body.get("items")
if not isinstance(raw_items, list):
    raw_items = body.get("data")
if isinstance(raw_items, list):
    items = [row for row in raw_items if isinstance(row, dict)]
```

No regression risk: prior endpoints used either bare lists or `items` envelopes; the new `data` fallback only activates when `items` is absent.

### `src/hb_assistant/procore/live_sync.py::_resolve_path`

Extended to substitute `{company_id}` alongside `{project_id}`:

```python
path = adapter.path_template
path = path.replace("{project_id}", procore_project_id)
path = path.replace("{company_id}", COMPANY_ID)
return path
```

The `COMPANY_ID = "5280"` constant (HB Construction) already exists at module scope.

### `src/hb_assistant/procore/live_sync.py::run_live_sync`

New activities special-case branch (parallel to meeting-detail):

```python
if adapter.endpoint_id == "activities" and items:
    activity_items: List[Dict[str, Any]] = []
    for schedule_summary in items:
        schedule_id = schedule_summary.get("schedule_id")
        activities_path = (
            f"/rest/v2.0/companies/{COMPANY_ID}/projects/{procore_project_id}"
            f"/schedules/{schedule_id}/activities"
        )
        activity_iter = list(client.paginate(activities_path, per_page=100, max_pages=3, max_items=200))
        for activity_raw in activity_iter:
            activity_raw.setdefault("schedule_id", schedule_id)
            activity_items.append(activity_raw)
    items = activity_items[:max_items]
```

The activities upsert derives `parent_procore_id` from `raw["schedule_id"]` so each child row links back to its source schedule.

The `meeting-detail` parent-list-override block was extended to also handle `activities` (same shape: list at `parent_path_template`, then per-item detail/sub-list).

## Adapter rows

```python
EndpointAdapter(
    endpoint_id="schedules",
    family="schedules",
    path_template="/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules",
    record_id_field="schedule_id",
    review_required_default=False, sensitivity="medium",
    live_verified=True,
    verification_reason="live_smoke_passed_2026-05-28:980e7fb0_v2_data_envelope",
)
EndpointAdapter(
    endpoint_id="activities",
    family="schedules",
    path_template="/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules/{schedule_id}/activities",
    parent_path_template="/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules",
    required_path_params=("project_id", "schedule_id"),
    record_id_field="activity_id",
    parent_record_id_field="schedule_id",
    review_required_default=False, sensitivity="medium",
    live_verified=True,
    verification_reason="live_smoke_passed_2026-05-28:6956f007_list_plus_n_per_schedule_notes_hashed",
)
```

## Normalizer field treatment

### `normalize_schedule`

| Source field | Treatment |
| --- | --- |
| `schedule_id`, `project_id`, `company_id` | Preserved verbatim (IDs) |
| `schedule_name`, `schedule_type` | Preserved verbatim |
| `is_active` | Preserved verbatim (bool) |
| `data_date`, `start_date` | Preserved verbatim (timestamps) |
| `calendar_id`, `parent_schedule_id` | Preserved verbatim |
| `created_at/by`, `updated_at/by`, `deleted_at/by` | Preserved verbatim (numeric user IDs are opaque) |

`review_required=False`; `routing_reason="schedules_structured_medium_sensitivity"`. The endpoint is operational scheduling data, no PII.

### `normalize_activity`

| Source field | Treatment |
| --- | --- |
| `activity_id`, `activity_name`, `parent_id` | Preserved verbatim |
| `start_date`, `finish_date`, `duration`, `duration_unit`, `duration_display_unit` | Preserved verbatim |
| `percent_complete`, `ordered_parent_index`, `constraint_type`, `constraint_date` | Preserved verbatim |
| `assigned_company`, `crew_size`, `calendar_id`, `deadline_date`, `deadline_variance` | Preserved verbatim |
| `is_critical`, `is_actual_start`, `is_actual_finish`, `total_float` | Preserved verbatim |
| `category_data` | Preserved verbatim (array of `{name, value}` short labels) |
| `resource_data` | Preserved verbatim (array of `{resource_id, resource_name}` short labels) |
| `notes` | SHA-256 `notes_summary` (`hash_prefix` + `length`); raw text NEVER persisted |
| `schedule_id`, `project_id`, `company_id` | Preserved verbatim |
| `created_at/by`, `updated_at/by` | Preserved verbatim |

`review_required=False`. The orchestrator passes `parent_procore_id = schedule_id` at upsert so each activity row carries its parent reference in the SQLite PK.

## Live verification

### Smoke

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint schedules \
  --confirm-live-get --json
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint activities \
  --confirm-live-get --json
```

| Endpoint   | receipt_id    | state    | request_count | retrieved |
| ---        | ---           | ---      | ---           | ---       |
| schedules  | `980e7fb0`    | success  | 1             | 1         |
| activities | `6956f007`    | success  | 4 (1 list + 3 paginated activities) | 10 |

### Apply (caps 1/5 then 3/100 then re-run)

**schedules**:

| Run            | receipt_id   | state    | upserted | total_after |
| ---            | ---          | ---      | ---      | ---         |
| Apply 1/5      | `3afaca38`   | success  | 1        | 1           |
| Apply 3/100    | `e15a76b4`   | success  | 1        | 1           |

Tropical has one schedule; the apply persists it with all 16 canonical schedule fields.

**activities**:

| Run                  | receipt_id   | state    | request_count | upserted | total_after |
| ---                  | ---          | ---      | ---           | ---      | ---         |
| Apply 1/5            | `7a46294e`   | success  | 4             | 5        | 5           |
| Idempotency 1/5      | `3d45f0c1`   | success  | (idempotent)  | 5        | 5           |

The single tropical schedule had > 5 activities; the cap truncated to the first 5. Each activity row carries `parent_procore_id = "9517"` (the tropical schedule id).

## SQLite state

```
schedules    : 1 row
activities   : 5 rows  (each linked to schedule 9517)
```

Sample schedule row:
```json
{"calendar_id": "16366", "company_id": "5280", "created_at": "2026-02-19T12:36:56Z",
 "created_by": "14517115", "data_date": "2026-01-29T13:00:00Z", "is_active": true,
 "project_id": "2525840", "schedule_id": "9517", "schedule_name": "Project",
 "schedule_type": "IMPORTED_READ_WRITE_PROJECT_SCHEDULE", "start_date": "2024-07-19T12:00:00Z", …}
```

Sample activity row (`procore_record_id=376321682`, `parent_procore_id=9517`):
```json
{"activity_id": "376321682",
 "activity_name": "Tropical World Nursery - U16 01/29/26 2026-02-23 19:43",
 "calendar_id": "16366", "category_data": [], "company_id": "5280",
 "constraint_date": "2024-07-19T12:00:00Z", "constraint_type": "startnoearlierthan",
 "created_at": "2026-02-23T19:43:43Z", "created_by": "12746745",
 "duration": 5271.0, "duration_display_unit": …}
```

## No-secret / no-raw-body attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id IN ('schedules','activities')
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id IN ('schedules','activities') AND raw_body_persisted != 0;
```
Result: `0`.

Activity `notes` free-text content is verified via the unit test fixture (`MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE` marker absent from `canonical_json_redacted` after upsert). The orchestrator's chain test asserts each activity row has `parent_procore_id` set to its source schedule_id.

## Test changes

- `tests/test_procore_schedule_normalizer.py` (NEW): 3 tests — structured-field preservation for schedule, structured + notes-hashed + nested-array-preserved for activity, and parent lineage fallback.
- `tests/test_procore_live_sync_verified_chain.py`: 2 new chain tests — schedules data-envelope unwrap, activities list+N+1 with `parent_procore_id` linking.
- `tests/test_procore_live_sync_verified_chain.py::_PathAwareFakeTransport`: extended to halt pagination on subsequent calls per URL (matches real Procore behavior; needed for the N+1 activities loop test which calls per-schedule URLs through the paginator).
- `tests/test_procore_endpoint_registry.py`: `_CANONICAL_IDS` 18 → 20; verified-set 18 → 20.
- `tests/test_procore_live_gate.py`: endpoints-list count 18 → 20.

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint schedules \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint activities \
  --apply --sqlite-only --max-pages 1 --max-items 5 \
  --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint schedules --json
hb-assistant procore live records count --project tropical --endpoint activities --json

python -m pytest -q tests/test_procore_schedule_normalizer.py \
                    tests/test_procore_live_sync_verified_chain.py \
                    tests/test_procore_endpoint_registry.py
```

Acceptance:
- schedules apply returns `state=success` with 1 row persisted; idempotent re-run.
- activities apply returns `state=success` with N rows persisted (capped by `--max-items`), each carrying `parent_procore_id = schedule_id`.
- All normalizer + chain tests pass.

## Final registry status

Phase 04A canonical registry: **20 endpoints, all live_verified=True**:

`projects`, `rfis`, `rfi-responses`, `submittals`, `submittal-responses`, `submittal-packages`, `meetings`, `meeting-topics`, `meeting-detail`, `observations`, `daily-log-weather`, `daily-log-manpower`, `daily-log-notes`, `daily-log-deliveries`, `daily-log-delays-review-routed`, `daily-log-inspections`, `daily-log-dcrs`, `punch-items`, **`schedules`** (new), **`activities`** (new).
