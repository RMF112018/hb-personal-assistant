# 04 — Scratch Root Setup

A bounded scratch app-support root was created for validation — **never** production app-support.

## Scratch root
```
scratch_root=/volume1/personal-assistant/app-support-smoke/n5b-20260704T082556Z
```
- Subdirs: `auth security db logs tmp evidence analytics cache`.
- Ownership + perms: `drwx------ personal-assistant-svc:users` (dirs `700`, files `600`).
- Guard: creation refused if the path already existed (`if sudo test -e "$SCRATCH"; then STOP`). Guard passed.

## Safety checks (scratch must hold no production/secret material)
```
scratch_has_production_sqlite=0
scratch_has_key_or_enc=0
scratch_config_file_count=2
svc_can_read_scratch_config=yes
```
- **No** production DB (`*.sqlite`), **no** Text Vault key (`*.key`), **no** `.enc` blobs, **no** token caches or
  secrets were placed in the scratch root.
- Only two non-secret, non-active scratch config files were written under `tmp/` (see `05`).

## Why `app-support-smoke/`
Per the runbook and prior guardrails, the production DB must never be opened writably and the app auto-migrates on a
normal connection. A separate `app-support-smoke/*` root keeps any config-driven path resolution away from the
production copied app-support (which holds the copied DB + Text Vault). This scratch root is inert: nothing was
started against it.
