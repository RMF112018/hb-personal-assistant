# local-sensitive/ (N8A) — gitignored, never committed

This directory holds raw runtime outputs and any NAS-specific identifiers that must **not** enter git
history. It is ignored by `.gitignore` (`/local-sensitive/` and `docs/evidence/**/local-sensitive/`).

## What belongs here (only when the live phase runs, with per-step approval)
- Raw SSH / command output from the read-only live-state reconciliation and the config-drift / cleanup
  steps (may contain the NAS hostname or the tailnet IP).
- Raw pre-edit backups of the live NAS config files (and their SHA-256, so committed evidence references
  them by hash only).
- Raw `sudo -l` / runner-status output and lock/lease payloads (contain the NAS hostname).
- Raw `PRAGMA` / row-count output that contains absolute NAS paths or the tailnet host/IP.

## What must NEVER be here or in committed evidence
- Token values, client secrets, `id_token`/`access_token`/`refresh_token`, MSAL cache contents.
- Text-Vault / Fernet keys, private keys / PEMs, tunnel or service-token / Cloudflare secrets.
- Decrypted confidential document text.

## Redaction note
`/volume1` and `/volume2` paths are **not** secrets and appear in the committed evidence where needed to
document the drift and dead-sudoers findings. The redaction targets are: NAS hostname, tailnet-IP literal,
secrets, keys, tokens, decrypted bodies, MSAL cache, Cloudflare secrets. Committed evidence references any
sensitive raw artifact **by name + SHA-256 only**.

## This session
Populated only if/when the operator-approved live phase runs; otherwise empty. Committed N8A evidence
references NAS parameters by name/structure and by hash only, and carries no secrets (see `08`).
