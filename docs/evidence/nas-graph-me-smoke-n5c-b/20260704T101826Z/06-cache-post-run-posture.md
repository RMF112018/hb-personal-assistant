# 06 — Cache Post-Run Posture

## Post-run cache/auth snapshot (operator)
| Item | Pre | Post | Delta |
|---|---|---|---|
| auth dir | `700 svc:users` | `700 svc:users` | none |
| token cache mode | `600` | `600` | none |
| token cache owner | `personal-assistant-svc:users` | `personal-assistant-svc:users` | none |
| token cache size | `9623` | `9623` | none |
| token cache mtime | `1783159254` | `1783159254` | none |
| svc cache readable | `yes` | `yes` | none |

## Interpretation
The token cache is **byte-for-byte unchanged** (same size, same mtime). The silent `acquire_token_silent` served a
still-valid access token from the cache **without** a network refresh, so MSAL did not rewrite the cache file this run.

Consequently the "cache changed / silent refresh occurred" WARN condition **does not apply**. The sole WARN driver for
N5C-B is the `--network host` requirement (bridge DNS instability). No token material left the container; ownership and
`600` perms are intact.
