# 03 — NAS Auth Path Preflight

Verified before login (operator sudo).

- **Auth dir:** `/volume1/personal-assistant/app-support/auth` = `mode=700 owner=personal-assistant-svc:users`.
- **Pre-existing cache:** `cache_preexisting=no` — no `msal-token-cache.bin` present before login (clean creation; no
  replacement authorization needed).
- **DB baseline:** captured `db_pre mtime + size` (size `4151631872`).
- **Image:** `hb-personal-assistant:nas` present (from N5C-R2).

## Config mounted (read-only)
- `/volume1/personal-assistant/config/hb-pa-config.yml` — confirmed **non-secret** (comments explicitly exclude
  secrets; grep found only `application_support_root` + `obsidian_vault` path keys, no secret values).
- `paths.application_support_root: /volume1/personal-assistant/app-support` — matches the app-support bind mount, so
  `PathPolicy` resolves the auth dir to the mounted NAS location and the cache persists to the NAS.
- `paths.obsidian_vault: /volume1/personal-assistant/app-support/_vault_disabled` — a disabled/placeholder vault path;
  irrelevant to `auth login` (login does not touch the vault). No temporary config was needed.
