# 12 — Rollback Plan

## This pass (planning)
Only evidence markdown was written (uncommitted). Rollback = delete
`docs/evidence/nas-vault-source-roots-n5/20260704T074519Z/`. Nothing else changed; no NAS/DB/vault state touched.

## Future N5A vault mirror (when authorized)
- **Copy-only**: the Mac vault is never modified and remains authoritative. Rollback = remove `<nas-vault-root>` on
  NAS and discard the config drafts. No DB change (no ingestion), no config activation → nothing to unwind in runtime.
- The NAS DB, Text Vault, and app-support are untouched by the vault mirror.

## Future syn-work repoint (when authorized)
- Repoint is a config `path` edit (same `source_root_key`, same rel_path tree) → `source_id` unchanged. Rollback =
  restore the prior `external_sources[*].path`. Because no NAS root is *activated* alongside the Mac root, there is no
  duplicate-record cleanup. If a copy-mirror was chosen instead, rollback = remove `source-roots/work` on NAS.

## Invariant
No rollback ever needs to touch the live Mac vault/source roots — they stay authoritative until a separate, explicit
activation/cutover phase.
