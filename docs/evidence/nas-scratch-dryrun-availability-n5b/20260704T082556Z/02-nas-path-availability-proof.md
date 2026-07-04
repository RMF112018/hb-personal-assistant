# 02 — NAS Path Availability Proof (metadata-only)

Non-sudo metadata checks via the `bfetting` SSH control path (`<nas-host>`, port 10021). Stat/count only — no file
contents read, no full `syn-work` enumeration.

## NAS vault mirror
```
/volume1/personal-assistant/vault          drwxr-x---  personal-assistant-svc:users
/volume1/personal-assistant/vault/obsidian drwxr-x---  personal-assistant-svc:users
vault_file_count=221
vault_md_count=155
```
- Exists, listable, least-privilege perms intact from N5A. File/md counts unchanged (`221` / `155`).
- (`bfetting` can read via `users` group membership — group `r-x` on `750`.)

## `syn-work` NAS-native root
```
/volume1/homes                    drwxrwxrwx  root:root
/volume1/homes/bfetting           drwxr-xr-x  bfetting:users
/volume1/homes/bfetting/Work      drwxrwxrwx  bfetting:users     <-- mode 777
syn_work_has_NAS_HB=yes
syn_work_has_Altman=yes
```
- Path exists; the two known top-level rel_path segments (`NAS - HB`, `Altman`) are present — consistent with the N5
  identity analysis (same rel_path tree → stable `source_id` on same-key repoint).
- **`Work` is mode `777`** — confirms the standing guardrail: the filesystem does **not** enforce read-only on
  `syn-work`. See `05` (schema finding) + `11` (activation gate).

## Scope discipline
Only top-level path existence + the two known segment names were checked. No recursive enumeration of `syn-work` was
performed (on-demand scandir hazard + bounded-scope discipline). Host shown as `<nas-host>` in committable evidence.
