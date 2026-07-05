# 13 — Negative Auth Tests

All against the real wired app under `remote_cloudflare` (origin auth hard-on). Every
negative case returns the identical `401 {"detail":"unauthorized"}` — the client cannot
tell them apart (no token-existence leak); the audit records the precise class.

| # | case | test | outcome |
|---|---|---|---|
| 1 | no `Authorization` header | `test_mcp_denied_without_auth` | 401 |
| 2 | non-Bearer scheme (`Basic …`) | `test_mcp_denied_bad_and_malformed_bearer` | 401 |
| 3 | empty `Bearer ` | `test_mcp_denied_bad_and_malformed_bearer` | 401 |
| 4 | unknown/garbage token | `test_mcp_denied_bad_and_malformed_bearer` | 401 |
| 5 | revoked token | `test_mcp_denied_revoked_and_expired` | 401 |
| 6 | expired token (time advanced) | `test_mcp_denied_revoked_and_expired` | 401 |

## Store-level negatives
| case | test | reason class |
|---|---|---|
| unknown token | `test_validate_roundtrip_and_unknown` | `unknown_token` |
| expired | `test_expired_token_denied` | `expired` |
| revoked (+ idempotent re-revoke false) | `test_revoked_token_denied` | `revoked` |
| rotate → old token dead | `test_rotate_revokes_old_mints_new` | old `revoked`, new `ok` |
| unknown client at mint | `test_create_rejects_unknown_client` | raises `OriginAuthError` |

## Hard-on invariant
`test_remote_profile_origin_auth_is_hard_on` — `HB_MCP_ORIGIN_AUTH_REQUIRED=0` cannot
disable origin auth in `remote_cloudflare`; only `local_trusted` honors the override.
