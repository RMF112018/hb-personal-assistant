# 10 — Rollback Plan

N5B created only scratch + evidence artifacts. Rollback is entirely NAS-scratch-side + repo-side, low-risk.

## Remove the scratch root (operator, sudo)
```bash
ssh -tt -p 10021 bfetting@<nas-host> '
  sudo rm -rf /volume1/personal-assistant/app-support-smoke/n5b-20260704T082556Z
  # optional: remove the empty parent if nothing else lives under it
  sudo rmdir /volume1/personal-assistant/app-support-smoke 2>/dev/null || true
'
```
This removes only the bounded scratch root (empty dirs + 2 non-secret config files). Nothing production is touched.

## Discard N5B evidence (agent)
The evidence bundle is uncommitted (untracked). Rollback = delete the directory:
```
docs/evidence/nas-scratch-dryrun-availability-n5b/20260704T082556Z/
```

## Do NOT remove (out of scope for N5B rollback)
- NAS mirrored vault from N5A (`/volume1/personal-assistant/vault/obsidian`)
- Text Vault material (`app-support/security/…`, N4A)
- copied DB (`app-support/db/…`, N3)
- production app-support
- Mac vault
- `/volume1/homes/bfetting/Work` (`syn-work`)

## Nothing else to revert
No production config was placed, no DB rows changed, no services started — so there is no runtime state to unwind.
