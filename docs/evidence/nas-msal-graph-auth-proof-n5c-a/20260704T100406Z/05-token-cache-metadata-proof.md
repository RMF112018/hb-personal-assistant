# 05 — Token Cache Metadata Proof (no contents)

Metadata only — the cache **contents were never read or printed**.

```
cache_exists=yes
mode=600
owner=personal-assistant-svc:users
size=9623
mtime=2026-07-04 10:00:54 UTC
```
- **Path:** `/volume1/personal-assistant/app-support/auth/msal-token-cache.bin`.
- **Owner/mode least-privilege:** `600` (owner-only read/write), owned by `personal-assistant-svc:users` — created
  correctly by the container's `--user 1028:100` mapping; no manual `chown`/`chmod` correction was needed.
- **Auth dir:** remains `mode=700 owner=personal-assistant-svc:users`.
- **Service-user read:** `svc_can_read_cache=yes` — the runtime service user can read its own cache.

## Interpretation
The delegated MSAL token cache exists on the NAS with correct least-privilege ownership and permissions, readable by
the runtime service user. This satisfies the N5C-A core objective. No cache correction step was required (owner/mode
were already `personal-assistant-svc:users` / `600`).
