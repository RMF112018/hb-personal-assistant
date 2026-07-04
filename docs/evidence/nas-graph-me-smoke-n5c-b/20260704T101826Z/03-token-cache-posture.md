# 03 — Token Cache Posture (pre-run)

The bounded `/me` smoke reuses the NAS-persisted MSAL delegated cache created in N5C-A. No re-login, no device code.

## Pre-run cache/auth posture (operator snapshot)
| Item | Value |
|---|---|
| auth dir | `700 personal-assistant-svc:users` |
| token cache mode | `600` |
| token cache owner | `personal-assistant-svc:users` |
| token cache size | `9623` |
| token cache mtime | `1783159254` |
| svc cache readable | `yes` |

The cache is svc-owned, group `users`, `600` (owner-only). The container runs `--user 1028:100`
(`personal-assistant-svc:users`) so it can read the cache; nothing else on the box can.

No cache **contents** were read or printed — only stat metadata. Token acquisition happens **inside** the container via
`acquire_token_silent`, which reads the cache file directly; the acquired token is never surfaced to evidence.
