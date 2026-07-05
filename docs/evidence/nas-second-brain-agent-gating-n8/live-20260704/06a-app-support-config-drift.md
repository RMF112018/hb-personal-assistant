# 06a — Open Finding: NAS configs still point app-support at `/volume1`

Surfaced during Proof 06 (the mutation-audit storage-guard failure). Recorded here as a separate, open,
actionable item — **not fixed** in this session.

## Finding
The service root was migrated `/volume1/personal-assistant` → `/volume2/personal-assistant`, but the live
NAS config files still set the app-support root to the old volume:

- `/volume2/personal-assistant/config/hb-pa-config.yml` → `paths.application_support_root: /volume1/personal-assistant/app-support`
- `/volume2/personal-assistant/config/hb-pa-config.mcp.yml` → `paths.application_support_root: /volume1/personal-assistant/app-support`

Both also carry `/volume1` `obsidian_vault` (`…/_vault_disabled`) values.

## Why it matters
Under `HB_NAS_RUNTIME=1` the storage guard approves only paths beneath `/volume2/personal-assistant/`. A
runtime loading either config would resolve `PathPolicy().get_app_support()` to a `/volume1` path and be
refused (`DbStorageGuardError`) on the first app-support-anchored write (e.g. the Obsidian mutation audit,
exactly the Proof 06 failure). The real app-support data lives at `/volume2/personal-assistant/app-support`.

## Current state
- No backend is running against these configs right now, so the drift is **latent**, not actively breaking.
- Proof 06 worked around it with a **container-only** minimal `HB_PA_CONFIG` pointing at
  `/volume2/personal-assistant/app-support`. **No live NAS config file was modified.**

## Recommended remediation (separate change, needs approval)
- Update `application_support_root` (and the `obsidian_vault` sentinel path) in the live NAS configs to
  `/volume2/personal-assistant/…`, consistent with the migrated service root and the storage guard.
- Verify against the committed deploy template (`deploy/nas/hb-pa-config.nas.example.yml`) so the example
  and the live configs agree on `/volume2`.

## Related open item
Separate from this: the stale `/volume1/personal-assistant/bin/hb-mcp-runner` sudoers rule (dead path) —
see `05a`. Both are `/volume1` residue from the migration and should be cleaned at N8 live-proof closeout.
