# 03 — Obsidian read/write parity

## Approach

NAS MCP preserves Mac Obsidian vault tool names and delegates to existing `obsidian_mcp` modules via `src/hb_assistant/nas_mcp/obsidian_adapter.py`. Vault root is container path `/mnt/vault` (host `/volume1/personal-assistant/vault/obsidian`).

Config guardrails (`deploy/nas/mcp/hb-pa-config.mcp.example.yml`):

- `writes_enabled: true`
- `vault_markdown_write_enabled: true`
- `allowed_write_file_types: [md]`
- `summarization_backend: deterministic` (no Ollama/LLM on NAS)
- `backup_dir: /app-support/audit/mcp/obsidian-backups` (container path)
- `support_dir: /app-support/audit/mcp/obsidian-support`

Env: `HB_OBSIDIAN_MCP_SUPPORT_DIR=/app-support/audit/mcp/obsidian-support` (compose).

## Enabled read tools (Mac names)

| Tool | Module | NAS notes |
|---|---|---|
| `list_directory` | `obsidian_mcp.tools` | Path redaction to `vault/...` |
| `search_vault` | `obsidian_mcp.tools` | Bounded lexical search |
| `read_file` | `obsidian_mcp.tools` | md/txt/pdf/docx bounded |
| `vault_read_frontmatter` | `obsidian_mcp.frontmatter` | — |
| `vault_search_by_properties` | `obsidian_mcp.frontmatter` | — |
| `vault_dataview_query` | `obsidian_mcp.frontmatter` | Constrained only |
| `vault_get_backlinks` | `obsidian_mcp.graph` | — |
| `vault_get_unlinked_mentions` | `obsidian_mcp.graph` | — |
| `vault_get_note_graph` | `obsidian_mcp.graph` | — |
| `vault_read_eml` | `obsidian_mcp.eml` | — |
| `vault_email_inventory` | `obsidian_mcp.eml` | — |
| `vault_parse_email` | `obsidian_mcp.eml` | — |
| `vault_extract_action_items` | `obsidian_mcp.domain` | — |
| `vault_extract_project_mentions` | `obsidian_mcp.domain` | — |

## Enabled with NAS guardrails

| Tool | Guardrail |
|---|---|
| `vault_map` | Read-only crawl; no curation apply |
| `vault_summarize_note` | `backend=None`; deterministic path only |
| `vault_summarize_folder` | `backend=None`; deterministic path only |
| `vault_project_status_summary` | Domain extraction; no model enrichment |

## Enabled write tools

| Tool | Policy |
|---|---|
| `create_note` | SHA optional on create; `caller_surface="nas_mcp"`; parent dir create allowed |
| `patch_note` | SHA-gated replace; backup under `/app-support/audit/mcp/...` |
| `vault_update_frontmatter` | SHA-gated; backup + receipt |
| `vault_create_note_from_template` | Template substitution only |
| `vault_append_to_daily_note` | Section-aware append |

## Plan-only (read); apply blocked

`vault_move_note_plan`, `vault_rename_note_plan`, `vault_archive_note_plan`, `vault_delete_note_plan`, `vault_curation_plan`, `vault_create_moc_plan`, `vault_auto_link_plan`, `vault_bulk_tagging_plan`, `vault_email_to_note_plan` — see `01-original-mac-obsidian-tool-audit.md`.

## Response normalization

All Obsidian adapter responses:

- Set `root_key: vault`
- Add `path_display: vault/<relative>`
- Reject responses containing `/volume1/` host paths (`host_path_leak` error)

## Local test evidence

| Test | File | Result |
|---|---|---|
| `create_note` stays in vault fixture | `tests/test_nas_mcp_files_rw.py::test_obsidian_create_note_stays_in_vault` | PASS |
| Blocked tool denied | `tests/test_nas_mcp_files_rw.py::test_obsidian_blocked_tool_denied` | PASS |
| 56-tool registry complete | `tests/test_nas_mcp_files_rw.py::test_mac_obsidian_tool_audit_registry_complete` | PASS |

## NAS functional proof

**Deferred** — MCP not restarted on NAS (sudo blocked). See `10-nas-reapply-proof.md`.
