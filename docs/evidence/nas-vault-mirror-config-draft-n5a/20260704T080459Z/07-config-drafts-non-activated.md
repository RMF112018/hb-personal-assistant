# 07 — Config Drafts (NON-ACTIVATED)

Two drafts live under `drafts/`. **Neither is placed at a runtime path, referenced by any env var, or activated.**
They are review artifacts toward N5B/N7. They contain **no secrets** (no bearer token, no client secret, no key material).

## `drafts/hb-pa-config.nas.n5a.draft.yml`
NAS runtime config draft. Key content:
- `paths.application_support_root: /volume1/personal-assistant/app-support` (N3/N4A DB + Text Vault resolve from here).
- `paths.obsidian_vault: /volume1/personal-assistant/vault/obsidian` (the mirror placed this pass).
- `security.microsoft_365_writeback_enabled: false`, `security.external_llm_enabled: false`.
- Notes reminding: keep background workers OFF on first NAS boot
  (`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`); secrets via env/protected files, never in YAML.
- **Non-activation:** the header says do NOT place at `/volume1/personal-assistant/config/hb-pa-config.yml` or set
  `HB_PA_CONFIG` yet.

## `drafts/obsidian_mcp_config.nas.n5a.draft.json`
Obsidian-MCP config draft. Key content:
- `vault_root: /volume1/personal-assistant/vault/obsidian`.
- **All ingestion/activation flags false:** `external_source_index_enabled`, `external_source_watch_enabled`,
  `source_card_auto_generate_enabled`, `source_summary_auto_generate_enabled`.
- `external_sources[0]`: `source_root_key: "syn-work"`, `path: /volume1/homes/bfetting/Work`, **`enabled: false`**,
  **`read_only: true`**, `source_kind: external_file`. Same `source_root_key` + same rel_path tree as the Mac root →
  `source_id` stays stable when eventually activated.
- No bearer token present.
- `_deferred`: `hb-onedrive` → Graph re-provision (N5C, not a filesystem root); scratch roots excluded.
- **Non-activation:** the `_draft_notice` says do NOT place at `<app-support>/analytics/obsidian_mcp_config.json`;
  because `enabled=false`/`read_only=true`, nothing registers or ingests even if a later phase copies it in before the
  identity-defect fix.

## Activation preconditions (documented, not performed here)
- The `source_id`-omits-`source_root_key` defect must be fixed before any multi-root NAS activation (see 08 + N8).
- `syn-work` must stay `read_only=True` while its path is mode `777` (see 08).
- Text Vault fail-closed startup preflight before production runtime.
