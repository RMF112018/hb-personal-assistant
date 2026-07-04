# 10 — Rollback Plan

N5A is copy-only + evidence. Nothing on the Mac or in any DB changed, so rollback is entirely NAS-side and low-risk.

## To undo the NAS mirror (operator, sudo)
```bash
ssh -tt -p 10021 bfetting@<nas-host> '
  sudo rm -rf /volume1/personal-assistant/vault/obsidian
  # optional: remove the empty parent if nothing else lives under it
  sudo rmdir /volume1/personal-assistant/vault 2>/dev/null || true
'
```
This removes only the mirrored copy. The Mac vault is authoritative and untouched.

## To undo the evidence (agent)
The evidence bundle is uncommitted (untracked). Rollback = delete the directory:
```
docs/evidence/nas-vault-mirror-config-draft-n5a/20260704T080459Z/
```

## Config drafts
The drafts were never placed/activated, so there is nothing to revert — discarding the `drafts/` files (or the whole
evidence dir) is sufficient.

## What rollback does NOT need to touch
- No DB rows (nothing registered/ingested).
- No Mac files.
- No running services (none started).
- No secrets/auth material (none written this pass; N4A's Text Vault placement is a separate, already-committed phase).
