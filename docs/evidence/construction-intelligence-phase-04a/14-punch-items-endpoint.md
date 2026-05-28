# Phase 04A — Add `punch-items` Endpoint

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)

An 18th canonical endpoint, `punch-items`, is added to the Phase 04A registry. The operator supplied the Procore v1.1 punch items list endpoint schema. The endpoint carries significant PII (people refs across `ball_in_court`, `created_by`, `closed_by`, `punch_item_manager`, `final_approver`, `assignees`, and per-assignment login information) and free-text bodies (`description`, `schedule_risk_reason`, `assignments[].comment`). All PII reduces to SHA-256 hash-only summaries; all free-text bodies reduce to `*_summary` hash structures; structured risk/financial fields are preserved verbatim for operator triage; `custom_fields` keep numeric/boolean/lov_entry values verbatim and hash string values.

## Outcome summary

| Metric                       | Value                                                                |
| ---                          | ---                                                                  |
| Endpoint added               | `punch-items` (registry row #18)                                     |
| Path                         | `/rest/v1.1/punch_items` (NO `{project_id}` placeholder)             |
| `project_id` passing         | **query parameter** (first Phase 04A endpoint with this pattern)     |
| Smoke receipt                | `0277eee6` (4 records, 1 HTTP request)                               |
| Apply 1/5 receipt            | `847d9e10` (4 records)                                               |
| Apply 3/100 receipt          | `76312dcd` (4 records, same)                                         |
| Idempotency 3/100 receipt    | `dac46704` (4 records, same)                                         |
| Rows persisted               | 4                                                                     |
| Verified set                 | 17 → **18**                                                          |

## Schema attribution

Operator-supplied Procore docs snippet (paraphrased; values not echoed):

```
GET /rest/v1.1/punch_items?project_id={n}&filters[...]
```

Returns a list of punch items per project (paginated). Each row carries:
- Structured fields: `id`, `name`, `reference`, `position`, `priority`, `private`, `status`, `workflow_status`, `due_date`, `created_at`/`updated_at`/`closed_at`/`deleted_at`, `has_resolved_responses`, `has_unresolved_responses`.
- Structured risk/financial signals: `cost_impact`, `cost_impact_amount`, `schedule_impact`, `schedule_impact_days`, `schedule_risk`, `schedule_risk_confidence`, `schedule_risk_probability`.
- Free-text: `description`, `schedule_risk_reason`, `assignments[].comment`.
- Short-label nested objects: `location` (id, name, code, parent_id), `trade` (id, name, active), `punch_item_type`, `cost_code`.
- People refs (PII): `ball_in_court[]`, `created_by`, `closed_by`, `punch_item_manager`, `final_approver`, `assignees[]`, `assignments[].login_information`.
- Variable-shape `custom_fields` keyed on `custom_field_<uuid>` with `{data_type, value}` entries.

## Field-by-field treatment

| Source field                              | Treatment                                                              |
| ---                                       | ---                                                                    |
| `id`, `name`, `reference`, `position`, `priority`, `private`, `status`, `workflow_status` | Preserved verbatim |
| Timestamps (`due_date`, `created_at`, `updated_at`, `closed_at`, `deleted_at`) | Preserved verbatim |
| `has_resolved_responses`, `has_unresolved_responses`       | Preserved verbatim                              |
| `cost_impact`, `cost_impact_amount`                        | Preserved verbatim (operator needs financial signal) |
| `schedule_impact`, `schedule_impact_days`, `schedule_risk`, `schedule_risk_confidence`, `schedule_risk_probability` | Preserved verbatim (risk-triage signals) |
| `description`                                              | SHA-256 `description_summary` (hash_prefix + length); raw text NEVER persisted |
| `schedule_risk_reason`                                     | SHA-256 `schedule_risk_reason_summary`                                |
| `location`, `trade`, `punch_item_type`, `cost_code`        | Preserved verbatim (short-label structured objects, no PII)            |
| `ball_in_court[]`, `created_by`, `closed_by`, `punch_item_manager`, `final_approver`, `assignees[]` | `*_summary: {count, hashed_identifiers: [{hash_prefix, id}, …]}` — `login` email or `name` reduced to SHA-256 prefix; numeric `id` preserved as opaque Procore identifier |
| `assignments[]`                                            | `assignments_summary: {count, items: [{id, approved, status, hashed_login, comment_summary, vendor, attachments_count, notified_at, responded_at, manager_accepted_at, updated_at}, …]}` |
| `assignments[].comment`                                    | SHA-256 `comment_summary`                                              |
| `assignments[].login_information`                          | SHA-256 `hashed_login` (login or name → 12-char hash prefix)           |
| `assignments[].vendor`                                     | Preserved verbatim (id + name only)                                    |
| `assignments[].attachments`                                | `attachments_count` (integer only)                                     |
| `custom_fields`                                            | `custom_fields_summary: {count, fields: {<key>: {data_type, value|value_summary}}}` — decimal/boolean/lov_entry values verbatim; string values hashed via `_hash_summary` |

## Code changes

### `src/hb_assistant/procore/normalizers/punch_item.py` (NEW)

- `normalize_punch_item` — main entry point.
- `_hash_summary` (free-text bodies), `_hash_identifier` (PII strings).
- `_person_hash_summary` / `_people_summary` for the various people refs.
- `_assignment_summary` / `_assignments_summary` for the per-assignment shape.
- `_custom_fields_summary` for the structured/hashed custom_fields handling.
- `_PUNCH_ITEM_STRUCTURED_KEYS` whitelist of always-preserved fields.
- Exported via `normalizers/__init__.py`.

### `src/hb_assistant/procore/endpoints.py`

- New `punch-items` adapter row: `family="punch_items"`, `path_template="/rest/v1.1/punch_items"` (no `{project_id}` placeholder), `sensitivity="high"`, `review_required_default=True`, `live_verified=True`, `verification_reason="live_smoke_passed_2026-05-28:0277eee6_pii_hashed_free_text_summaries"`.

### `src/hb_assistant/procore/live_sync.py`

- `_NORMALIZER_BY_ID["punch-items"] = normalize_punch_item`.
- No orchestrator branch added: the existing parent-only flow handles `punch-items` directly. The orchestrator's existing `params={"project_id": ...} if "{project_id}" not in path else None` branch correctly routes `project_id` as a query parameter when the path template has no placeholder.

## Live verification

### Smoke

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint punch-items \
  --confirm-live-get --json
```

- `receipt_id`: `0277eee6-3a2e-4190-90be-7fbf0078390f`
- `state`: `success` · `status`: `success`
- `request_count`: 1 · `retrieved_count`: 4 · `normalized_count`: 4
- `redacted_errors`: `[]`

### Apply (caps 1/5)

- `receipt_id`: `847d9e10-1efe-4b4a-9972-798c6dfa7787`
- `state`: `success`
- `request_count`: 1
- `sqlite_upserted_count`: 4 · `sqlite_total_count_after`: 4

### Apply (caps 3/100, E2E target)

- `receipt_id`: `76312dcd-118e-4b05-a5ce-6ad2128edd58`
- `state`: `success`
- `request_count`: 3 (paginated retries to cover up to 3 pages)
- `sqlite_upserted_count`: 4 (UPSERT — same 4 rows)

### Idempotency re-run (caps 3/100)

- `receipt_id`: `dac46704-8cb8-4b3b-b2c8-27b95f20b85c`
- `state`: `success`
- `sqlite_upserted_count`: 4 · `sqlite_total_count_after`: 4

The upsert PK preserves idempotency across re-runs.

## SQLite state

```
punch-items   : 4 rows
```

All 4 rows carry `review_required=1` (PII bearing → always routed to review).

## PII redaction attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='punch-items'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='punch-items' AND canonical_json_redacted LIKE '%@%';
```
Result: **`0`** — no `@` characters in any punch-items canonical row. All people emails are reduced to SHA-256 `hash_prefix` strings; raw email text never persists. The 12-character hex hash prefixes never contain `@`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='punch-items' AND raw_body_persisted != 0;
```
Result: `0`.

Sample row (truncated `canonical_json_redacted` for punch item 67895268):

```json
{
  "assignees_summary": {
    "count": 1,
    "hashed_identifiers": [{"hash_prefix": "8858ade73480", "id": 3475896}]
  },
  "assignments_summary": {
    "count": 1,
    "items": [{
      "approved": false,
      "attachments_count": 0,
      "hashed_login": {"hash_prefix": "8858ade73480", "id": 3475896},
      "id": 94492871,
      "notified_at": "2025-08-05T14:52:56Z",
      "status": "unresolved",
      "updated_at": "2025-08-05T14:52:56Z",
      "vendor": {"id": 3256...
```

People summaries carry only `hash_prefix` (12-char hex) + opaque numeric `id`. Vendor (a short-label structured object) is preserved verbatim. Assignment `comment` and punch-item `description` are reduced to `comment_summary` / `description_summary` hash structures.

## Test changes

- `tests/test_procore_punch_item_normalizer.py` (NEW): 3 tests — structured-field preservation + PII redaction, free-text hashing, custom_fields structured/hashed treatment.
- `tests/test_procore_live_sync_verified_chain.py`: added `test_punch_items_apply_persists_with_pii_hashed_and_bodies_summarized` — synthetic punch item with PII + free text; FakeTransport assertion that `params["project_id"]` is set (query-param path) and no email/name/free-text appears in canonical JSON.
- `tests/test_procore_endpoint_registry.py`: `_CANONICAL_IDS` 17 → 18, verified-set 17 → 18.
- `tests/test_procore_live_gate.py`: endpoints-list count 17 → 18.

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint punch-items \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint punch-items --json

python -m pytest -q tests/test_procore_punch_item_normalizer.py \
                    tests/test_procore_live_sync_verified_chain.py \
                    tests/test_procore_endpoint_registry.py
```

Acceptance:
- punch-items apply returns `state=success` with single-page retrieval.
- Records count returns ≥ 1.
- Re-run holds the row count.
- All punch-item normalizer + chain tests pass.

## Final registry status

Phase 04A canonical registry: **18 endpoints, all live_verified=True**:

`projects`, `rfis`, `rfi-responses`, `submittals`, `submittal-responses`, `submittal-packages`, `meetings`, `meeting-topics`, `meeting-detail`, `observations`, `daily-log-weather`, `daily-log-manpower`, `daily-log-notes`, `daily-log-deliveries`, `daily-log-delays-review-routed`, `daily-log-inspections`, `daily-log-dcrs`, **`punch-items`** (new).
