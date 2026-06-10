# 02 — Schema decision and source-quality precedence

## Schema decision: V46 retained (no V47)

V46 `procore_endpoint_raw_payloads` already provides every required column:
`source_quality TEXT NOT NULL`, `raw_procore_payload_persisted INTEGER CHECK(IN (0,1))`,
`payload_json TEXT NOT NULL`, `payload_hash`, `redaction_status`, `security_scrub_status`,
`contains_signed_url`, `contains_secret_like_value`, `external_writeback_performed CHECK(=0)`,
and `UNIQUE(endpoint_key, project_key, parent_record_id, record_id, payload_hash)`. The 43
`procore_raw_*` structured tables carry `source_quality`, `amount`, `raw_payload_id` (FK),
`is_current`, `daily_brief_eligible`. No additive column is needed; precedence is enforced
in application code. `LATEST_SCHEMA_VERSION` stays **46** (the V46 migration assertion is
unchanged and still passes).

## Source-quality precedence

```
SOURCE_QUALITY_RANK = {live_full_payload: 100, fixture_full_payload: 90, redacted_legacy_projection: 10}
```

Rules (enforced in code, anchored on the structured `record_key`, which excludes
`payload_hash`):

- higher rank wins (full overwrites legacy structured row in place);
- equal rank → idempotent upsert;
- lower rank → skip raw + structured, report `skipped_due_to_higher_quality`;
- legacy replay after a full row exists is a no-op (checked via
  `_existing_source_quality_rank` and `_existing_raw_full_rank`, parent `'' → NULL` normalized).

## Migration safety

No migration added. Applying the migrator to a production copy returned head `46`
(additive no-op). Existing idempotency and exact-row foundation tests pass unchanged.
