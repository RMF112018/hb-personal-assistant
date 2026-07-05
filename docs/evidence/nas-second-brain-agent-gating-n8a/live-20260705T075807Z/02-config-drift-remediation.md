# 02 — Config-Drift Remediation

**Outcome: NO EDIT REQUIRED — the drift was already resolved on the live NAS.**

## Approved plan (from Bobby)
Fix `application_support_root` (and the `obsidian_vault` sentinel) from `/volume1/personal-assistant/app-support` to `/volume2/…` in the two live NAS configs, preserving `_vault_disabled`, matching `deploy/nas/hb-pa-config.nas.example.yml`.

## Finding
Read-only inspection (`01-live-state-reconciliation.md` §2) shows both live configs **already** point at `/volume2`:
- `…/config/hb-pa-config.yml`: `application_support_root: /volume2/personal-assistant/app-support`; `obsidian_vault: /volume2/personal-assistant/app-support/_vault_disabled` (**sentinel intact**).
- `…/config/hb-pa-config.mcp.yml`: `application_support_root: /volume2/personal-assistant/app-support`.
- No `/volume1/personal-assistant` token remains in either file.

This equals the committed template `deploy/nas/hb-pa-config.nas.example.yml` (`application_support_root: /volume2/personal-assistant/app-support`, vault `…/_vault_disabled`). The committed N8 finding `06a` (drift open) is **stale**; the drift was corrected in a prior session ("resolved, verify on next boot") and is verified at rest here.

## Action taken
None. No config file was modified; no backup was needed because no edit occurred. The `_vault_disabled` sentinel is preserved and vault writes remain disabled — the goal (app-support root on `/volume2`, no new vault-write enablement) is already satisfied.

## Verdict
**Closed (already remediated).** Storage-guard alignment confirmed: a runtime loading either config under `HB_NAS_RUNTIME=1` would resolve app-support under `/volume2/personal-assistant/` and pass the guard — the root cause of the Proof-06 stop-condition no longer exists.
