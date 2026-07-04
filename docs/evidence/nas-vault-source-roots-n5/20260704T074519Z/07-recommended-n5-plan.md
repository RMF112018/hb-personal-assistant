# 07 — Recommended N5 Plan

## Recommendation: N5A = Mirror vault + non-activated config draft (Options A+B)

### Operator steps (when N5A authorized)
1. `syn-work` strategy — **RESOLVED**: repoint to the operator-confirmed NAS-native path `/volume1/homes/bfetting/Work`
   (same rel_path tree, svc-readable) — no copy. (Config-draft edit only in N5A; activation deferred.)
2. Run/paste privileged NAS placement steps for the vault mirror (svc-owned dirs need interactive sudo, as in N3/N4A).

### Local-agent steps (when N5A authorized)
1. Mirror `<mac-obsidian-vault>` (4.9 MB) → NAS: build a clean `ustar` bundle in scratch, tar-stream over the ssh
   **exec** channel (no SFTP) to a bfetting-writable NAS tmp, verify by hash; operator sudo places under
   `<nas-vault-root>` with least-privilege owner/perms.
2. Author NAS config **drafts** in scratch (not placed): `config.yml` with `paths.obsidian_vault=<nas-vault-root>`;
   `obsidian_mcp_config.json` draft with same-key `external_sources[*].path` set to NAS bases (absolute; validator
   requires absolute). Keep `external_source_watch_enabled=false`, index/auto-gen off; set
   `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` for any future quiet boot.
3. (N5B) Prove reachability with `obsidian_source_root_availability_probe.py` (stat-only) against NAS paths — no
   ingestion, no card-gen, no writable DB open, no `SQLiteMigrator.apply()`.

### Guardrails
Same `source_root_key` + identical rel_path tree; never Mac + NAS roots active together; Mac vault stays authoritative;
no config placement/activation in N5A (drafts only).

## Explicitly deferred
- `syn-work` repoint config edit → included in N5A config draft (path resolved: `/volume1/homes/bfetting/Work`); activation still deferred.
- `hb-onedrive` → Graph re-provision (08) + N8 activation.
- Ingestion / card-gen / watcher / scheduler → N8.
- Source-identity defect fix + Text Vault fail-closed hardening → code-change authorization (10).
