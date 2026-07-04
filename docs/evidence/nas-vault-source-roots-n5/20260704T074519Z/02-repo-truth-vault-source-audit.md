# 02 — Repo-Truth Vault / Source Audit

## Vault addressing
- Config `paths.obsidian_vault` (`config/models.py:35`, default hard-coded Mac); resolved `PathPolicy.get_vault_root()`
  (`config/path_policy.py:141`). Loader order defaults → `config/config.yml` (absent) → `HB_PA_CONFIG` (`loader.py:49`).
- All vault subfolders are **vault-relative** config strings (`source_notes_folder`, `Email Archive`, daily, etc.).
  Every read/write resolves through `resolve_safe_path()` (`tools.py:44`) under `config.vault_root`. **Move is transparent.**
- MCP mirror `ObsidianMcpConfig.vault_root` inherits the same default (`obsidian_mcp/config.py:87`).
- Dead doc: `.env.example:19 HB_PERSONAL_ASSISTANT_VAULT` is never read — do not rely on it.

## Note content is relocation-safe
- Card frontmatter (`source_notes.py:128-159`): `source_path: <rel_path>` + `source_root_key` (relative/logical),
  plus hashes/ids (`source_sha256`, `source_mtime_ns`, `source_id`). **No absolute Mac paths, no `file://`/`obsidian://`.**
- Bodies link by rel_path/source_id; a card "describes and links back to an indexed source — NOT a copy".

## Source identity (critical)
`source_id = sha256("{source_kind}|file|{rel_path}")[:32]` (`obsidian_mcp/source_index_repository.py:38`); `rel_path`
= `abs_path.relative_to(root.path)` (`source_indexer.py:187`). Unique index `(source_kind, rel_path)`
(`store/source_intelligence_tables.py:110`). Omits `source_root_key` and absolute path; `abs_path_hash` stored but
**never read**. All child tables (`source_intelligence_metadata/text/chunks/relationships/generated_notes/summaries`)
FK on `source_id`.

## Two source-root systems
- **A. Obsidian-MCP `external_sources[]`** (`obsidian_mcp/config.py:64-81`): `ExternalSourceRoot{source_root_key,
  path[absolute-validated], enabled, source_kind}`. Persisted in `<app-support>/analytics/obsidian_mcp_config.json`
  (0600; may hold bearer token) + projected to DB `source_intelligence_state` at startup. Flags
  `external_source_index_enabled=True`, `external_source_watch_enabled=False`.
- **B. Construction SharePoint/OneDrive registry** (`resources/config/sharepoint_onedrive_sources.seed.yaml`,
  DB `construction_source_locations`): Graph-keyed (web_url/drive_id/site_id) — **not local-path identity** — plus 3
  OneDrive `local_sync_path` CloudStorage roots.

## Registration / ingestion / card-gen writes
- Root registration → DB `source_intelligence_state` (gated: workers-enabled AND `external_source_index_enabled`);
  watcher `.start()` gated by `external_source_watch_enabled` (default False). Registration path lives in the JSON config;
  DB caches keys+enabled (`api.py:729-758`, `source_index_repository.py:89`).
- Ingestion scan writes `source_intelligence_*`; card-gen writes one vault md + `source_intelligence_generated_notes`.
  Auto-gen flags default OFF (`source_card_auto_generate_enabled`, `source_summary_auto_generate_enabled`, watch).

## Hard-coded Mac paths that break on NAS (runtime)
`models.py:35` vault default · `models.py:34` app_support (`~/Library/…`; NAS config overrides to `/volume1/...`) ·
OneDrive `local_sync_path` (`sharepoint_onedrive_sources.seed.yaml:270,290,308`) · app-only cert paths
(`cli/auth.py:32`, `graph/proof_runner.py:21`, proof/admin only) · macOS `launchd` scheduler (no Linux equivalent).

## Safe read-only tools (reuse)
`scripts/obsidian_source_root_availability_probe.py` (stat-only default) · `obsidian_source_first_indexing_dryrun.py`
(no DB/card/queue) · `obsidian_vault_db_reconcile.py` (report). Prove reachability/preview without ingesting.
