# 18 — Sensitive / Redaction Scan

## Automated gate — `tests/test_repo_sensitive_scan.py`
The repo-wide gate is RED on **16 pre-existing findings**, all in files unrelated to this phase
(procore/obsidian/phase_10/local-model/CFR-subrepo/frontend synthetic test fixtures &
redaction-proof corpora — not real secrets). **None of the 16 are in any phase-touched file.**
This is the same pre-existing state recorded in the origin-auth bundle; per Bobby's instruction
the allowlist is not modified for unrelated fixtures.

## Phase-added findings: ZERO unallowed
The scanner flags 4 lines in phase files — all `env_secret_assignment` / `msal_cache_content`,
both in `_BROADLY_ALLOWED_RULES` (keyword noise on the pre-existing `msal-token-cache`/
`refresh_token`/`access_token` denylist constants in `config.py` and a test `Bearer <fixture>`
header). None are real secrets; none fail the gate (`any unallowed in phase files: []`).

## Manual scan of new files
`limits.py`, `overrides.py`, `override_cli.py`, `freshness.py`, and the new test file: no NAS
hostname, no tailnet-IP literal, no token/secret/key, no decrypted content, no raw source
payloads. Freshness output is aggregate-only and asserted path-free
(`test_freshness_output_has_no_local_paths`). Override records contain no credential.

## Redaction posture
Committed evidence carries no raw token/secret/key, no NAS hostname, no tailnet IP, no payloads.
`redact_text` is applied to freshness error-class fields. `/volume1`/`/volume2`, `127.0.0.1`,
`8765`, and `mcp.bobby-fetting.me` are non-secret structural constants.
