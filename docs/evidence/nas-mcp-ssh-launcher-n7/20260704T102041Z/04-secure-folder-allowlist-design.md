# 04 — Secure folder allowlist design

## Root keys (config-driven)

| root_key | Container mount | Host (example) |
|---|---|---|
| `vault` | `/mnt/vault` | `/volume1/personal-assistant/vault/obsidian` |
| `syn-work` | `/mnt/source-roots/syn-work` | `/volume1/homes/bfetting/Work` |

## Tools

- `hb_secure_list`, `hb_secure_stat`, `hb_secure_read_excerpt` (any root_key)
- `hb_vault_search`, `hb_vault_read_excerpt` (vault)
- `hb_source_root_search`, `hb_source_root_read_excerpt` (syn-work default)

## Deny rules

- Absolute paths, `..` traversal, symlink escape (no follow on list)
- Denied segments: `auth`, `security`, `secrets`, `.git`, etc.
- Denied patterns: `.enc`, token/cache/key patterns
- Binary files denied for excerpt reads
- Max excerpt: 16 KB (configurable)
- Responses use **relative paths** only
