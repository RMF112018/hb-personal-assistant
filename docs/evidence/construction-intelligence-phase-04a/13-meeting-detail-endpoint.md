# Phase 04A — Add `meeting-detail` Endpoint

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)

A 17th canonical endpoint, `meeting-detail`, is added to the Phase 04A registry. The operator supplied the Procore v1.1 meeting DETAIL endpoint schema; the endpoint provides a richer per-meeting view than the existing list endpoint, including PII-bearing fields (attendees, topic assignments) and HTML free-text (`minutes`, `description`, `conclusion`). All PII is reduced to SHA-256 hash-only summaries; all free-text bodies are reduced to `*_summary` hash structures; the `remote_meeting_url` is path-only with query strings stripped.

## Outcome summary

| Metric                                  | Value                                                          |
| ---                                     | ---                                                            |
| Endpoint added                          | `meeting-detail` (registry row #17)                            |
| Path (detail)                           | `/rest/v1.1/projects/{project_id}/meetings/{id}`               |
| Path (parent list)                      | `/rest/v1.1/projects/{project_id}/meetings`                    |
| Dispatch                                | List → flatten → N+1 detail fetch                              |
| Smoke receipt                           | `7eaf5ae6` (10 records, 11 HTTP requests)                      |
| Apply receipt                           | `3425a0e6` (5 parents + 98 nested topics, 6 HTTP requests)     |
| Idempotency receipt                     | `09724adc` (5 + 98, same caps)                                 |
| meeting-detail rows persisted           | 5                                                              |
| meeting-topics rows added via detail    | 98 (extracted from `meeting_categories[].meeting_topic[]`)     |
| Verified set                            | 16 → **17**                                                    |

## Schema attribution (operator-provided snippet)

The operator supplied a snippet from Procore docs:

```
GET /rest/v1.1/projects/{project_id}/meetings/{id}
```

Key top-level keys observed in the example payload: `id`, `meeting_template_id`, `position`, `created_by_id`, `title`, `location`, `occurred`, `starts_at`, `ends_at`, `time_zone`, `is_private`, `is_draft`, `mode`, `created_at`, `updated_at`, `description`, `conclusion`, `remote_meeting_url`, `attachments`, `attendees`, `meeting_categories`. Each `meeting_categories[]` entry has its own `meeting_topic[]` array (the standalone-list endpoint at `/meeting_topics` does not return categories or this nested structure).

## Field-by-field treatment

| Source field                          | Treatment                                                                 |
| ---                                   | ---                                                                       |
| `id`, `meeting_template_id`, `position`, `created_by_id` | Preserved verbatim                                          |
| `title`, `location`, `time_zone`, `mode` | Preserved verbatim                                                     |
| `is_private`, `is_draft`, `occurred`  | Preserved verbatim                                                        |
| `starts_at`, `ends_at`, `created_at`, `updated_at` | Preserved verbatim                                            |
| `description`                         | SHA-256 `description_summary` (hash_prefix + length); raw text NEVER persisted |
| `conclusion`                          | SHA-256 `conclusion_summary`; raw text NEVER persisted                    |
| `remote_meeting_url`                  | `remote_meeting_url_redacted` — path-only (query strings stripped)        |
| `attendees[]`                         | `attendees_summary: {count, hashed_identifiers: [{hash_prefix, status, attendee_id}, …]}` — `login_information.login` (email) and `name` reduced to SHA-256 hash_prefix; numeric `id` preserved as `attendee_id` |
| `attachments[]`                       | `attachments_count` (integer only)                                        |
| `meeting_categories[]`                | `meeting_categories_count` + `category_titles` (short labels only)        |
| `meeting_categories[].meeting_topic[]` | Each topic extracted via `extract_topics_from_categories()` and upserted under `endpoint_id="meeting-topics"` with `parent_procore_id=<meeting_id>`. Reuses `normalize_meeting_topic` which already applies hash-only treatment to topic `minutes` / `description` / `action_items`. |
| `meeting_topic[].assignments[]`       | Reduced via `_assignments_summary` to `{count, hashed_identifiers: [{hash_prefix, assignment_id}, …]}` — applied per-topic at the orchestrator's topic-normalization step (assignments live inside each topic dict) |

## Code changes

### `src/hb_assistant/procore/normalizers/meeting.py`

- `normalize_meeting_detail` — new normalizer with the rich schema + PII/free-text/URL redaction.
- `_attendees_summary`, `_assignments_summary`, `_redact_remote_meeting_url` — private helpers.
- `_hash_identifier` — SHA-256 hash-only helper for PII strings (email, name).
- `extract_topics_from_categories(raw)` — public helper that walks `meeting_categories[].meeting_topic[]` (handles list + single-dict shapes).
- All exported via `normalizers/__init__.py`.

### `src/hb_assistant/procore/endpoints.py`

- New `meeting-detail` adapter row: family=`meetings`, sensitivity=`high`, `review_required_default=True`, path=`/rest/v1.1/projects/{project_id}/meetings/{id}`, parent_path_template=`/rest/v1.1/projects/{project_id}/meetings`. `live_verified=True` with reason `live_smoke_passed_2026-05-28:7eaf5ae6_list_plus_n_detail_with_pii_hashed_summaries`.

### `src/hb_assistant/procore/live_sync.py`

- `_NORMALIZER_BY_ID["meeting-detail"] = normalize_meeting_detail`.
- **Path override**: for `adapter.endpoint_id == "meeting-detail"`, the initial paginate uses `parent_path_template` (the list endpoint).
- **v1.1 grouped flatten** extended to cover `meeting-detail` (the list response is the same as `meetings`).
- **N+1 detail loop**: after items are flattened, for each meeting issue a single GET to `f"/rest/v1.1/projects/{procore_project_id}/meetings/{meeting_id}"` and REPLACE the items list with the detail payloads. Rate-limit / 5xx on individual detail calls record a `detail_transport_error` in `redacted_errors` and the loop continues.
- **Child dispatch hardcode**: `_resolve_child_adapter` doesn't return meeting-topics for meeting-detail because meeting-topics now has `parent_record_id_field=None` (standalone). A small special-case forces `child_adapter = endpoints.get("meeting-topics")` and `child_normalizer = normalize_meeting_topic` for the meeting-detail dispatch.
- **Inline child extraction**: when `adapter.endpoint_id == "meeting-detail"`, `raw_children = extract_topics_from_categories(raw)` (two-level nested walk) instead of the single-field `raw.get(child_field)` used by other parents.

## Live verification

### Smoke

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint meeting-detail \
  --confirm-live-get --json
```

- `receipt_id`: `7eaf5ae6-7e9e-4040-86f0-71975e708790`
- `state`: `success` · `status`: `success`
- `request_count`: 11 (1 list + 10 detail)
- `retrieved_count`: 10 · `normalized_count`: 10
- `redacted_errors`: `[]`

### Apply (caps 1/5 — conservative first apply)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint meeting-detail \
  --apply --sqlite-only --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

- `receipt_id`: `3425a0e6-673f-41fe-b55e-4427a76caaca`
- `state`: `success` · `status`: `success`
- `request_count`: 6 (1 list + 5 detail)
- `parent_upserted_count`: 5 (meeting-detail rows)
- `child_endpoint_id`: `meeting-topics`
- `child_retrieved_count`: 98 · `child_normalized_count`: 98 · `child_upserted_count`: 98 · `child_errors_count`: 0
- `sqlite_upserted_count`: 103 (5 + 98)
- `sqlite_total_count_after`: 5 (per-endpoint count for meeting-detail)

The 5 meetings averaged **~20 topics each** — the detail endpoint surfaces significantly more granular meeting structure than the standalone list.

### Idempotency re-run (caps 1/5)

- `receipt_id`: `09724adc-0c35-4388-8232-75f672ed1935`
- `state`: `success`
- `parent_upserted_count`: 5 · `child_upserted_count`: 98 (UPSERT, no new INSERT)
- `sqlite_total_count_after`: 5 (unchanged)

The upsert PK `(project_key, endpoint_id, parent_procore_id, procore_record_id)` correctly handles re-runs without duplication. The N+1 cost is paid again on each apply (5 detail GETs per run) but persistence stays idempotent.

## SQLite state

```
meeting-detail   : 5 rows
meeting-topics   : 108 rows (was 10 standalone + 98 newly from detail extraction)
meetings         : 96 rows (unchanged)
```

## PII redaction attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='meeting-detail'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='meeting-detail' AND canonical_json_redacted LIKE '%@%';
```
Result: **`0`** — no `@` character appears in any meeting-detail canonical row. Attendee and assignee emails are fully reduced to SHA-256 `hash_prefix` strings; no raw email text persists. (The 12-character hex hash prefixes never contain `@`.)

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='meeting-detail' AND raw_body_persisted != 0;
```
Result: `0`.

Sample meeting-detail row (truncated `canonical_json_redacted` for meeting 12888268):

```json
{
  "attachments_count": 0,
  "attendees_summary": {
    "count": 15,
    "hashed_identifiers": [
      {"attendee_id": 184006571, "hash_prefix": "4b1704dee6cf"},
      {"attendee_id": 184006570, "hash_prefix": "bf6498993b22"},
      …
    ]
  },
  …
}
```

Sample meeting-topic row 184029786 (extracted from meeting 12888268's nested categories):

```json
{"id": 184029786, "parent_meeting_id": "12888268", "status": "Open", "title": "Change Orders"}
```

The `parent_procore_id` column in the row equals `12888268` — the parent meeting id — so the meeting-topic row is correctly linked back to its source meeting-detail row.

## Test changes

- `tests/test_procore_meeting_normalizer.py`: added `test_normalize_meeting_detail_carries_rich_schema_and_redacts_pii` (asserts PII-free serialization, hashed identifiers, query-stripped URL, structural counts) and `test_normalize_meeting_detail_extracts_nested_topics_from_categories` (asserts the categories→topics walker).
- `tests/test_procore_live_sync_verified_chain.py`: added `test_meeting_detail_apply_persists_meeting_and_nested_topics` (FakeTransport-driven list+detail flow, asserts parent + child counts, PII-free canonical content).
- `tests/test_procore_endpoint_registry.py`: `_CANONICAL_IDS` 16 → 17; verified-set test 16 → 17.
- `tests/test_procore_live_gate.py`: endpoints-list count 16 → 17.

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint meeting-detail \
  --apply --sqlite-only --max-pages 1 --max-items 5 \
  --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint meeting-detail --json
hb-assistant procore live records count --project tropical --endpoint meeting-topics --json

python -m pytest -q tests/test_procore_meeting_normalizer.py \
                    tests/test_procore_live_sync_verified_chain.py \
                    tests/test_procore_endpoint_registry.py
```

Acceptance:
- meeting-detail apply returns `state=success` with `request_count = 1 + N` where N is the number of meetings fetched.
- meeting-detail row count ≥ 1; meeting-topics count grows by ~20 per meeting on the first apply.
- Re-run at the same caps holds row counts.
- All meeting-detail + new chain tests pass.

## Final registry status

Phase 04A canonical registry: **17 endpoints, all live_verified=True**:

`projects`, `rfis`, `rfi-responses`, `submittals`, `submittal-responses`, `submittal-packages`, `meetings`, `meeting-topics`, **`meeting-detail`** (new), `observations`, `daily-log-weather`, `daily-log-manpower`, `daily-log-notes`, `daily-log-deliveries`, `daily-log-delays-review-routed`, `daily-log-inspections`, `daily-log-dcrs`.
