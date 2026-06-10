# 00 — Repo Truth Baseline

## Branch / base
- Branch: `fix/procore-endpoint-specific-structured-projections`
- Base SHA: `ed4645023f410322d26d27e872faab7d2bfce6ab` (main, after PR #18)
- Schema head before this change: **V46** (`LATEST_SCHEMA_VERSION = 46`)
- Schema head after this change: **V47**

## PR #18 behavior confirmed
- Full raw payloads persist to `procore_endpoint_raw_payloads.payload_json` with
  `raw_procore_payload_persisted = 1` and `security_scrub_status = transport_secrets_removed`.
- Source-quality precedence: `SOURCE_QUALITY_RANK` = `{live_full_payload: 100,
  fixture_full_payload: 90, redacted_legacy_projection: 10}`; `_rank` / `_existing_*_rank`
  prevent a lower-rank write from downgrading a higher-rank row.
- Transport-secret scrubber `scrub_transport_secrets` drops credential keys
  (`AUTH_SECRET_KEY_RE`) and strips signed-URL credential params; preserved verbatim.
- No raw body emission outside the local DB.

## Procore code paths inventoried
- `src/hb_assistant/procore/structured_analytics.py` — full-raw persistence
  (`upsert_full_raw_payload_and_structured`), generic bronze projection
  (`_structured_values_from_payload`), backfill, scrubber, precedence.
- `src/hb_assistant/procore/endpoints.py` — 59-entry adapter registry (`list_all`/`get`).
- `src/hb_assistant/store/migrator.py` — additive versioned migrations (V1…V46),
  `LATEST_SCHEMA_VERSION`.
- `src/hb_assistant/cli/procore.py` — `procore analytics` subgroup.
- Generic bronze layer (V46): 44 `procore_raw_*` tables sharing ONE shallow flat schema
  (the defect this package remediates).

## Mechanically-measured scope (from `PathPolicy().get_db_path()`)
- Production DB = the PLAIN app-support root (matches the validation checklist).
- Endpoints with full raw payloads (`raw_procore_payload_persisted = 1`) at remediation
  time: **36**, then **37** after a daily refresh also captured a `projects` full payload.
- Distinct `(endpoint, json_path)` pairs observed: **2,439** across 37 endpoints.
- Endpoints with only `redacted_legacy_projection` (no full payload this pass, status
  `no_full_payload_available`): activities, budget-detail-columns, budget-detail-rows,
  commitment-change-order-line-items, meeting-detail, meeting-topics, rfi-responses,
  submittal-packages, subcontractor-invoice-contract-items.

## Output of this change (V47)
- 37 endpoint-specific primary tables + 41 nested child/detail tables = **78
  `procore_ep_*` tables**, generated deterministically from the committed projection
  registry. All V46/V7 tables retained (additive only).
