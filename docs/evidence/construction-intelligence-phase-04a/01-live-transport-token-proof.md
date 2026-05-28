# Phase 04A — Live Transport Token Proof

Prompt 03B per-endpoint live sync evidence. Demonstrates that the live
transport carries an OAuth **access token** (never client secret, never
refresh token, never raw OAuth payload) and that the surface is GET-only.

## Construction guarantees

| Concern | Source | Evidence |
| --- | --- | --- |
| Bearer header uses access token only | `src/hb_assistant/procore/http_client.py::_build_headers` (line 88) | `Authorization: Bearer <access_token>` built per request; token never stored on client instance |
| Client secret is never bearer-substituted | `src/hb_assistant/procore/http_client.py` module docstring + Phase 04A doctrine | No import of `PROCORE_CLIENT_SECRET` in `http_client.py`. Verified in `tests/test_procore_client_secret_isolation.py` |
| Token sourced from access-token provider chain | `src/hb_assistant/procore/token_provider.py::default_procore_token_provider` | EnvOrKeychain -> RefreshingOAuth -> Missing; refresh failure returns `None` (fail-closed) |
| GET-only enforcement | `ProcoreHTTPClient._require_get` (http_client.py:79) | Raises `ProcoreAPIError(code="method_not_allowed")` on non-GET |
| Redacted source URL only | `src/hb_assistant/procore/redaction.py::redact_source_url` | Strips host + query; persisted into `procore_live_records.source_url_redacted` |
| Schema-level constraints | `src/hb_assistant/store/migrator.py::V6_STATEMENTS` | `redaction_applied CHECK = 1`, `raw_body_persisted CHECK = 0` on every Phase 04A table |

## Fake-transport receipt (representative)

Captured by `tests/test_procore_live_sync_verified_chain.py::test_transport_receives_bearer_access_token_not_client_secret`:

- `PROCORE_ACCESS_TOKEN=synthetic-bearer-token`
- `PROCORE_CLIENT_SECRET=MUST_NEVER_APPEAR_IN_AUTH_HEADER` (planted)
- Observed `Authorization` header on the GET: `Bearer synthetic-bearer-token`
- Observed HTTP method: `GET` (asserted across every transport call)
- Observed body of `procore_live_records.canonical_json_redacted`: no `Bearer`, no token literal

## Redacted command receipt shape (representative)

```json
{
  "receipt_id": "...",
  "phase": "phase04a",
  "mode": "live_apply",
  "command_endpoint": "rfis",
  "endpoint_id": "rfis",
  "legacy_endpoint_alias": "list-rfis",
  "company_id": "5280",
  "project_key": "tropical",
  "procore_project_id": "2525840",
  "endpoint_family": "rfis",
  "http_method": "GET",
  "request_count": 1,
  "retrieved_count": 2,
  "normalized_count": 2,
  "sqlite_upserted_count": 2,
  "sqlite_total_count_after": 2,
  "raw_body_persisted": false,
  "secrets_redacted": true,
  "state": "success",
  "status": "success",
  "reason_codes": [],
  "no_live_call_performed": false
}
```

No raw Procore response body, no OAuth token literal, no client secret literal
appears in receipt, evidence, log, or persisted SQLite row.
