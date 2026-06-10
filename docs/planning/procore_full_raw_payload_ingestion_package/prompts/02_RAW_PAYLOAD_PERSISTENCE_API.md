# 02 — Full raw payload persistence API

## Objective

Create a reusable API to write full endpoint item payloads into `procore_endpoint_raw_payloads` and project matching `procore_raw_*` rows.

## Preferred target

`src/hb_assistant/procore/structured_analytics.py`

## Required API shape

Implement a function equivalent to:

```python
def upsert_full_raw_payload_and_structured(
    *,
    db_path: str | Path | None,
    endpoint_id: str,
    project_key: str,
    procore_project_id: str | None,
    raw_item: dict[str, Any],
    parent_procore_id: str | None = None,
    fetched_at_utc: str | None = None,
    source_quality: str = "live_full_payload",
    capture_run_id: str | None = None,
) -> dict[str, Any]:
    ...
```

Exact signature may differ, but it must support full raw item dict, endpoint id, project key, Procore project id, optional parent id, timestamps, DB path, and source-quality override for tests.

## Behavior

The API must:

1. resolve endpoint adapter and structured table;
2. determine stable record id;
3. compute raw payload id, source ref hash, request fingerprint hash, payload hash, payload size;
4. insert/update `procore_endpoint_raw_payloads` with `payload_json` from the full endpoint item;
5. insert/update the endpoint-family `procore_raw_*` table from the full endpoint item;
6. insert/update dimensions as applicable;
7. honor source-quality precedence;
8. return a receipt with counts and source-quality classification.

## Secret handling

Do not store transport/auth secrets. Add a guard/scrubber for:

- Authorization;
- bearer tokens;
- access_token;
- refresh_token;
- client_secret;
- api_key.

Do not remove Procore business values simply because they include people, company names, text, financial values, nested objects, attachment metadata, or custom fields.

## Placeholder handling for structured fields

Structured scalar extraction must treat these as missing:

- `NULL`;
- `null`;
- `None`;
- empty string;
- `[redacted]`;
- `[scrubbed]`;
- `REDACTED`;
- empty object/list where a scalar is expected.

Do not mutate the stored full payload JSON for these business values; this rule applies to structured projection quality.

## Tests

Use fixture payloads proving:

- full payload JSON persists;
- structured fields populate from full payload;
- auth/transport fields are not stored;
- placeholder strings do not populate structured scalars;
- legacy fallback still works.

## Evidence

Write `docs/evidence/procore_full_raw_payload_ingestion/03-full-raw-fixture-proof.md` with only counts, field names, hashes, and populated/non-null counts.
