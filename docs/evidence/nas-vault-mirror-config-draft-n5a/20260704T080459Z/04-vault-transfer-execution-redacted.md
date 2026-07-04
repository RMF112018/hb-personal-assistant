# 04 — Vault Transfer Execution (redacted)

## Tar build (local, agent)
- Built with `COPYFILE_DISABLE=1 tar --format gnutar --exclude '.DS_Store' -C <mac-obsidian-vault> -cf <tar> .`
- **Format choice:** `gnutar`. A first attempt with `--format ustar` failed with *"Pathname too long"* and silently
  dropped the single longest-path note (154/220 instead of 155/221); the vault's longest path (~204 chars) exceeds
  ustar's ~100/255-char limits. `gnutar` supports long names and extracts cleanly under GNU `tar` on the Synology.
  `COPYFILE_DISABLE=1` suppresses macOS AppleDouble/xattr sidecar records (which the NAS GNU tar would otherwise list
  as phantom duplicate entries, as seen in N4A).
- Local tar: **284 entries** (221 files + 63 dirs), **155 md**, **0 `.DS_Store`**.
- Local tar sha256 prefix: `2a07970d47a2cdef…` (full value in `local-sensitive/`).

## Transfer (no SFTP)
- Streamed over the SSH exec channel: `ssh -p 10021 bfetting@<nas-host> "cat > <nas-tmp-gnu>" < <tar>`.
- Landed at `/volume1/personal-assistant/app-support/tmp/n5a-obsidian-vault-gnu-20260704T075500Z.tar`.
- Integrity: NAS-side sha256 of the streamed tar **matched** the local tar sha (sha_match=YES); NAS-side gnutar
  listing showed **155 md**. (A stale earlier `ustar` staging file with a different sha was superseded by this
  gnutar tar and was not used.)

## Operator sudo extraction (privileged)
Operator ran the provided single block; observed output:
- Guard passed — `vault/obsidian` was absent before placement.
- Created + extracted the tar under `vault/obsidian`.
- Applied ownership `personal-assistant-svc:users` and perms dirs `750` / files `640` recursively over
  `/volume1/personal-assistant/vault`.
- Removed the temp tar (`rm -f <nas-tmp-gnu>`).
- Post-copy counts: `nas_file_count=221`, `nas_md_count=155`.
- Service-user read: `svc_can_stat_dir=yes`, `svc_md_count=155`.

Redaction: NAS host shown as `<nas-host>`; Mac vault path as `<mac-obsidian-vault>`; sha shown as a prefix only.
