# 05 — NAS Vault Permissions Proof

Least-privilege ownership/perms applied and confirmed by the operator's placement output.

## Ownership + directory modes
```
/volume1/personal-assistant/vault          drwxr-x---  personal-assistant-svc:users
/volume1/personal-assistant/vault/obsidian drwxr-x---  personal-assistant-svc:users
```
- All directories: `750` (`rwxr-x---`).
- All files: `640` (`rw-r-----`).
- Owner: `personal-assistant-svc`; group: `users`.

## What this enforces
- **Owner (`personal-assistant-svc`)**: read + traverse directories, read files → the future runtime can read notes.
- **Group (`users`)**: read + traverse dirs, read files — no write.
- **Others**: no access.
- No world-writable bits (contrast the `syn-work` root at mode `777`, see 08). The vault mirror is properly locked down.

## Traverse chain (svc can reach the vault)
`/volume1` → `/volume1/personal-assistant` → `/volume1/personal-assistant/vault` (owned svc, `750`) →
`.../vault/obsidian` (owned svc, `750`). Because svc owns `vault` and `obsidian`, the owner `x` bit grants traversal.

## Service-user read proof
Run as the demoted service user:
```
svc_can_stat_dir=yes
svc_md_count=155
```
The service user can stat the vault directory and enumerate all 155 markdown notes — read access confirmed without
granting write.
