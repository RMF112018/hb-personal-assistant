# 07 — No-leak scan

## Commands

```bash
git diff --name-only origin/main...HEAD
git grep -n -E "Bearer |access_token|refresh_token|client_secret|X-Amz-|SharedAccessSignature|https://[^ ]*\?.*(token|sig|signature)=" -- \
  src/hb_assistant/procore/structured_analytics.py \
  src/hb_assistant/procore/live_sync.py \
  src/hb_assistant/cli/procore.py \
  docs/evidence/procore_full_raw_payload_ingestion
find docs/evidence/procore_full_raw_payload_ingestion -type f \
  \( -name "*.json" -o -name "*.db" -o -name "*.sqlite" -o -name "*.payload" \) -print
```

## Findings and classification

All matches in `src/` are **detector literals** or **pre-existing auth-status code**, not
real leaks:

- `structured_analytics.py` — the scrubber's own regexes and the
  `_CREDENTIAL_QUERY_PARAM_NAMES` / `AUTH_SECRET_KEY_RE` constants (the code that *removes*
  secrets), plus the existing `no_raw_leak_scan` detector pattern literals.
- `cli/procore.py` / `live_sync.py` — pre-existing OAuth status code: token-provider
  wiring (`access_token_provider=…`), cache-presence flags (`access_token_present`,
  `refresh_token_cached`), and reason strings. No secret values.
- `tests/test_procore_full_raw_payload_ingestion.py` — synthetic fixture placeholders
  (`AT-SECRET-VALUE`, `LIVE-SECRET-TOKEN`, `DEADBEEF`, `X-Amz-Signature`) used to prove
  scrubbing; not real credentials.

No real `Bearer <token>` values, OAuth tokens, client secrets, API keys, or live signed
URLs are present in source, tests, or evidence.

## Artifact scan

`find docs/evidence/...` for `*.json` / `*.db` / `*.sqlite` / `*.payload` → **no files**.
No DB files, raw payload dumps, or token-like values are committed. `/tmp` DB copy used
for validation was removed.
