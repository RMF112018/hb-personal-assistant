# Finding: `source-watch` sees 0 roots — config file absent (not a deploy defect)

## Observation

```
source-watch status                    -> roots: []
bootstrap --dry-run --all-roots        -> root_count: 0
```

## Root cause (traced in code, confirmed on NAS)

`source-watch` reads roots from `obsidian_mcp.config.load_config().external_sources`
(`src/hb_assistant/cli/source_watch.py:34` → `obsidian_mcp/config.py:451`). That loader reads a
persisted JSON at:

```
config_path() = <app_support>/analytics/obsidian_mcp_config.json
             = /volume2/personal-assistant/app-support/analytics/obsidian_mcp_config.json
```

On the NAS that file **does not exist** (`ls: No such file or directory`), so `load_config()` returns
a default `ObsidianMcpConfig()` with `external_sources = []`. Hence 0 roots.

This is consistent with the project posture: V117 is the watcher-**readiness** slice — the capability
is deployed, but the source roots have never been operationally registered on this NAS. The dry-run
did exactly its job: surfaced that no roots are wired **before** any apply. `bootstrap --all-roots`
apply would be a genuine no-op today.

## Two consequences for the roots-configuration task

1. **The config JSON must be authored** (`05-external-sources-config-draft.*`). It only needs
   `external_sources` (plus `schema_version`); every other obsidian-MCP setting stays at its current
   default (the file's absence means all defaults are already in effect).

2. **Execution context matters.** The internet-facing MCP container mounts only
   `vault/obsidian → /mnt/vault`, `Home → /mnt/roots/home`, `Work → /mnt/roots/work` — at *different*
   container paths, and does **not** mount the Backup path at all. So `bootstrap` cannot be run via
   `docker exec` into the live MCP container for these host-path roots. It must run in a **dedicated,
   short-lived operator container** that bind-mounts the real host roots (read-only) at their real
   paths plus the live DB (rw) — matching the "populated OUTSIDE the request path / out-of-band"
   design (`store/source_structure_tables.py` v115 note). See the draft runbook in `05-…`.

## Dotfile exclusion is automatic

`source_indexer.should_ignore()` calls `pathsafe.path_blocked(rel_path, include_hidden=False)`, which
blocks any dot-prefixed path segment. So dot-prefixed files/folders are skipped on **every** root by
default — the Backup root's "exclude anything starting with `.`" requirement needs no extra config.
