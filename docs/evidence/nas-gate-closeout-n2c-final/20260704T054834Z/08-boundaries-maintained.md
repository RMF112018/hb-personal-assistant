# N2C-V · 08 — Boundaries Maintained

Every constraint held across N2C-S/T/U and this N2C-V closeout:

## Data / DB
- ❌ Did NOT copy the live Mac DB. ❌ Did NOT copy any DB to the NAS.
- ❌ Did NOT open or migrate any production/copied DB. (N2 schema work used **scratch** `tmp_path`
  DBs only.)
- ❌ Did NOT run a copied-DB smoke.

## Secrets / credentials
- ❌ Did NOT copy or read secrets, MSAL token caches, Procore credentials, Fernet keys, or
  Text-Vault keys/blobs.
- ❌ No passwords requested in chat, echoed, or written to disk. Where root was needed
  (`synofirewall`), the **operator** ran it interactively and pasted non-secret output.

## Backend / services
- ❌ Did NOT start the HB backend or any container. ❌ Did NOT restart Portainer.
- ❌ Did NOT enable schedulers/watchers/workers/automation loops/source-root ingestion.

## Vault / source roots
- ❌ Did NOT write into the live Obsidian vault. ❌ Did NOT mount live vault or source roots.

## Network / infra changes THIS phase
- This phase made **no** router/firewall/Tailscale changes — read-only corroboration only
  (svc-SSH probe; UPnP SSDP enumeration). Earlier network changes (UPnP map deletion in N2C-T;
  UPnP disable and firewall apply in N2C-U) were done under explicit per-action operator
  authorization at the time.
- ❌ Agent did NOT run sudo.

## Evidence hygiene
- WAN IP masked as `98.x.x.183` in all committed evidence; full IP + raw InternetDB JSON only in
  gitignored `local-sensitive/` (`docs/evidence/**/local-sensitive/`).
- ❌ No credentials/cookies/tokens/login screenshots recorded.

## Git
- ❌ Nothing committed or pushed for N2C-S/T/U/V. Evidence is uncommitted in the worktree awaiting
  explicit authorization (see `09-git-status.md`).
