# 01 — Schema and source-quality strategy

## Objective

Decide whether V46 is sufficient or V47 is needed, and implement source-quality precedence so full raw rows cannot be overwritten by redacted legacy replay.

## Inspect

Inspect V46 columns and constraints for:

- `procore_endpoint_raw_payloads.payload_json`;
- `source_quality`;
- `raw_procore_payload_persisted`;
- `redaction_status`;
- `security_scrub_status`;
- `payload_hash`;
- `raw_payload_id`;
- conflict keys in `procore_endpoint_raw_payloads` and `procore_raw_*` tables.

## Preferred outcome

Stay on V46 if possible.

Use:

- `source_quality='live_full_payload'` for full endpoint response rows;
- `raw_procore_payload_persisted=1` for live full payload rows;
- `source_quality='redacted_legacy_projection'` and `raw_procore_payload_persisted=0` for legacy replay.

## Add V47 only if necessary

Add V47 only if current columns cannot safely represent source-quality/provenance or precedence. If added, migration must be additive only.

Possible additive fields:

- `payload_origin`;
- `source_quality_rank`;
- `business_payload_persisted`;
- `transport_secret_status`.

Do not add fields without a clear need.

## Source-quality precedence

Implement a helper such as:

```python
SOURCE_QUALITY_RANK = {
    "live_full_payload": 100,
    "fixture_full_payload": 90,
    "redacted_legacy_projection": 10,
}
```

Rules:

- same-quality reruns are idempotent;
- higher quality updates lower quality;
- lower quality never overwrites higher quality;
- legacy replay after live full payload exists must be skipped or no-op;
- receipts must report `skipped_due_to_higher_quality`.

## Tests

Prove source-quality rank, upgrade, no downgrade, idempotency, and migration safety.

## Evidence

Write `docs/evidence/procore_full_raw_payload_ingestion/02-schema-source-quality.md` with schema decision and precedence proof.
