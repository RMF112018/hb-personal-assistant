# DRAFT for review — `external_sources` roots config (NOT applied)

Companion to `05-external-sources-config-draft.json`. This is a **proposal** for the roots-configuration
task. Nothing here has been written to the NAS. Applying it (and running bootstrap) is a **separate
gate** requiring your authorization.

The JSON validates against the live `ObsidianMcpConfig` schema (verified with
`ObsidianMcpConfig.model_validate`).

## Proposed roots

| key | host path | sensitive | notes |
| --- | --- | --- | --- |
| `vault` | `/volume2/personal-assistant/vault` | false | the PA vault area |
| `work` | `/volume1/homes/bfetting/Work` | false | business documents |
| `home` | `/volume1/homes/bfetting/Home` | **true** | personal — flagged sensitive |
| `macbook_backup` | `/volume1/homes/bfetting/Backup/MacBook-Pro.local/Users/bobbyfetting` | **true** | personal MacBook backup |

Watcher stays **OFF** (`external_source_watch_enabled: false`); indexing is enabled
(`external_source_index_enabled: true`). Dot-prefixed files/folders are **automatically excluded** on
every root (indexer `should_ignore` → `path_blocked(include_hidden=False)`), so the Backup root's
"exclude anything starting with `.`" requirement needs no extra config.

## Review points (please confirm before this is applied)

1. **`sensitive` flags** — I set `home` and `macbook_backup` to `sensitive: true` (personal content),
   `vault` and `work` to `false`. `sensitive` affects downstream carding/summary handling. Adjust to
   your intent.
2. **`source_root_key` names** — stable identifiers used in all read surfaces and reconciliation
   receipts. Renaming later re-keys state, so pick final names now.
3. **`vault` path** — you specified `/volume2/personal-assistant/vault`. Note the MCP compose mounts
   `/volume2/personal-assistant/vault/obsidian` as the Obsidian vault. Confirm whether you want the
   whole `vault/` tree indexed as an external source, or just `vault/obsidian`.
4. **Scale** — `external_source_scan_max_files` defaults to **5000**. A MacBook backup of a full user
   home can be far larger; a dry-run will report the counts. We may need to raise this cap or scope
   the Backup root to specific subfolders before an apply.
5. **Structure-root mapping** — bootstrap resolves a structure key per file-root. With no explicit
   `--structure-root-map-json`, each root maps to itself; confirm if any file-root should share a
   structure-root.

## Execution model (important — do NOT `docker exec` the live MCP for these)

The internet-facing MCP container mounts only `vault/obsidian → /mnt/vault`, `Home → /mnt/roots/home`,
`Work → /mnt/roots/work` (different container paths) and does **not** mount the Backup path. Since these
roots use **host** paths, `bootstrap` must run in a **dedicated, short-lived operator container** that
bind-mounts the real host roots read-only at their real paths, plus the live DB `:rw` — the same
pattern as the migrate/snapshot steps, and matching the "out-of-band" design.

### Proposed apply runbook (for when authorized — dry-run first)

1. Write the reviewed JSON to
   `/volume2/personal-assistant/app-support/analytics/obsidian_mcp_config.json`
   (owner `1028:100`, mode `600`). The analytics dir already exists (compose RW mount).
2. **Dry-run** in an operator container (read-only walk; NO writes):
   ```sh
   sudo /usr/local/bin/docker run --rm -i --user 1028:100 -e HB_NAS_RUNTIME=1 \
     -v /volume2/personal-assistant/app-support/db:/volume2/personal-assistant/app-support/db:rw \
     -v /volume2/personal-assistant/app-support/analytics:/volume2/personal-assistant/app-support/analytics:rw \
     -v /volume2/personal-assistant/vault:/volume2/personal-assistant/vault:ro \
     -v /volume1/homes/bfetting/Work:/volume1/homes/bfetting/Work:ro \
     -v /volume1/homes/bfetting/Home:/volume1/homes/bfetting/Home:ro \
     -v /volume1/homes/bfetting/Backup:/volume1/homes/bfetting/Backup:ro \
     hb-personal-assistant:nas \
     hb-assistant source-watch bootstrap --dry-run --all-roots --json
   ```
   Review the per-root counts (files seen / would-index) and the resolved paths.
3. Only after review + explicit authorization, drop `--dry-run` to apply. Then refresh the RO snapshot
   (`snapshot-mcp-db.sh`) so the MCP serves the new index. Watcher + cron remain separately gated.

> Note: an apply writes bootstrap state + index rows to the **live** DB. Take a fresh DB backup first
> (same posture as the deploy), and keep the snapshot refresh as the final step.
