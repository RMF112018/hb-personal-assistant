# 05 — Proposed NAS Path Map

NAS-local filesystem only. **Nothing created this pass.**

| Logical | Proposed NAS path | Migration class | Notes |
|---|---|---|---|
| Obsidian vault (`__vault_notes__`) | `/volume1/personal-assistant/vault/obsidian` | **mirror (copy)** | absent today; 4.9 MB; vault-relative → transparent |
| `syn-work` (+ attachments) | **`/volume1/homes/bfetting/Work`** (operator-confirmed NAS-native) | **repoint (no copy)** | top-level `NAS - HB`+`Altman` matches rel_path tree; svc-readable (777/755/777 traverse chain); register `read_only=True` |
| `hb-onedrive` | — (no NAS filesystem) | **Graph re-provision** | OneDrive/cloud; via delegated MSAL (Files.ReadWrite.All), not a copy |
| `docs-test` / `manual-test` | — | ignore | scratch |
| app-support (unchanged) | `/volume1/personal-assistant/app-support` | done (N3/N4A) | DB + Text Vault already here |

## Constraints (all honored by the plan)
- NAS-local FS only; **no SQLite over SMB/NFS**.
- No raw vault / DSM / SMB / WebDAV / Cloudflare exposure of these folders.
- Service user `personal-assistant-svc` least-privilege (read approved notes/roots); dirs `700`/files `600` where sensitive.
- Control user `bfetting` deploys/manages via SSH; privileged placement via interactive sudo (as N3/N4A).
- Future MCP (N7) reads notes/roots as svc; future watchers (N8) must avoid Mac/NAS dual ingestion.
- Preserve rel_path trees where identity depends on them (§04).
- **Old Mac roots and new NAS roots must never be active as equivalent source roots simultaneously.**
- **`/volume1/homes/bfetting/Work` is mode `777` — permissions do NOT enforce read-only.** Register the `syn-work`
  root `read_only=True` and run no write-capable workflow against it unless the perms or a bind-mount control are
  tightened separately. (svc-readability comes from the others-x/r bits, not from a dedicated ACL.)

## Vault-root strategy
Set `paths.obsidian_vault` → `<nas-vault-root>` via a NAS `config.yml` (or `HB_PA_CONFIG`); MCP `vault_root` inherits.
Config draft only in N5A — not placed/activated until a later authorized phase.
