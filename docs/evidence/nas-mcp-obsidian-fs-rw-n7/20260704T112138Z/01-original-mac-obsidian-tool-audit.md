# Original Mac Obsidian MCP Tool Audit (NAS Disposition)

**Evidence run:** `20260704T112138Z`  
**Scope:** All 56 tools in `src/hb_assistant/obsidian_mcp/tools.py` `_TOOL_REGISTRY`, cross-referenced with `src/hb_assistant/nas_mcp/obsidian_adapter.py` `NAS_OBSIDIAN_BLOCKED` and Mac OAuth scopes in `src/hb_assistant/obsidian_mcp/mcp_app.py` `_TOOL_SCOPES`.

## Vault paths

| Surface | Config source | Resolved path | Notes |
|---------|---------------|---------------|-------|
| **Mac Obsidian MCP** | `ObsidianMcpConfig.vault_root` → `PathPolicy().get_vault_root()` → `config.paths.obsidian_vault` | `~/Documents/Obsidian Vault` (example: `config/config.example.yml`) | Local UI-managed MCP server; absolute host paths returned in tool responses. |
| **NAS MCP (container)** | `mcp.obsidian.vault_root` or fallback `roots.vault.mount` | `/mnt/vault` (`deploy/nas/mcp/hb-pa-config.mcp.example.yml`) | Container-relative vault root; responses normalized to `vault/<relative>` with host `/volume1/...` redacted. |
| **NAS MCP (host mount)** | Docker compose `HB_VAULT_MOUNT` | `/volume1/personal-assistant/vault/obsidian` → `/mnt/vault:rw` (`deploy/nas/mcp/compose-mcp.yaml`) | Synology host path bind-mounted into the MCP container. Mac vault fragment `Documents/Obsidian Vault` must **not** appear in NAS compose. |

## Disposition legend

| Disposition | Meaning on NAS MCP |
|-------------|-------------------|
| **enable on NAS** | Dispatched via `obsidian_adapter._dispatch_obsidian` handlers; subject to NAS write policy (`writes_enabled`, `vault_markdown_write_enabled`, SHA-gated mutations, path redaction). |
| **enable with NAS guardrails** | Enabled but constrained (e.g. `summarization_backend: deterministic` only; no Ollama/model paths on NAS). |
| **plan-only / read-only only** | Plan tools run read-only; no matching `*_apply` handler enabled on NAS without separate approval. |
| **blocked pending approval** | Raises `ObsidianMcpToolError("blocked_on_nas", …)` per `NAS_OBSIDIAN_BLOCKED`. |
| **not applicable to NAS** | No NAS handler and not in blocked map (none of the 56 registry tools fall here). |

## Full tool disposition table (56 tools)

Mac scope values derive from `_TOOL_SCOPES`: `obsidian.read` → **read**, `obsidian.write` → **write**.

| tool_name | mac_scope | disposition | reason / approval condition |
|-----------|-----------|-------------|----------------------------|
| list_directory | read | enable on NAS | — |
| search_vault | read | enable on NAS | — |
| read_file | read | enable on NAS | — |
| create_note | write | enable on NAS | SHA-gated; `caller_surface="nas_mcp"`; requires `writes_enabled` + `vault_markdown_write_enabled` |
| patch_note | write | enable on NAS | SHA-gated whole-file replace; `caller_surface="nas_mcp"` |
| vault_map | read | enable with NAS guardrails | Read-only crawl; respect `include_hidden=false` default; path redaction enforced |
| vault_summarize_note | read | enable with NAS guardrails | `summarization_backend: deterministic` only (`backend=None` forced in adapter) |
| vault_summarize_folder | read | enable with NAS guardrails | `summarization_backend: deterministic` only (`backend=None` forced in adapter) |
| vault_read_eml | read | enable on NAS | — |
| vault_email_inventory | read | enable on NAS | — |
| vault_parse_email | read | enable on NAS | — |
| vault_read_frontmatter | read | enable on NAS | — |
| vault_update_frontmatter | write | enable on NAS | SHA-gated; backup + receipt; `caller_surface="nas_mcp"` |
| vault_search_by_properties | read | enable on NAS | — |
| vault_dataview_query | read | enable on NAS | Constrained query only (no arbitrary Dataview execution) |
| vault_get_backlinks | read | enable on NAS | — |
| vault_get_unlinked_mentions | read | enable on NAS | — |
| vault_get_note_graph | read | enable on NAS | — |
| vault_create_note_from_template | write | enable on NAS | No code execution; `caller_surface="nas_mcp"` |
| vault_append_to_daily_note | write | enable on NAS | Section-aware append; backup + receipt; `caller_surface="nas_mcp"` |
| vault_move_note_plan | read | plan-only / read-only only | Apply counterpart blocked; preview only |
| vault_move_note_apply | write | blocked pending approval | destructive apply blocked; requires separate operator approval for NAS move apply |
| vault_rename_note_plan | read | plan-only / read-only only | Apply counterpart blocked; preview only |
| vault_rename_note_apply | write | blocked pending approval | destructive apply blocked; requires separate operator approval for NAS rename apply |
| vault_archive_note_plan | read | plan-only / read-only only | Apply counterpart blocked; preview only |
| vault_archive_note_apply | write | blocked pending approval | destructive apply blocked; requires separate operator approval for NAS archive apply |
| vault_delete_note_plan | read | plan-only / read-only only | Returns archive plan substitute; no permanent delete |
| vault_semantic_search | read | blocked pending approval | semantic search requires source index; blocked pending approval |
| vault_extract_action_items | read | enable on NAS | — |
| vault_project_status_summary | read | enable with NAS guardrails | Deterministic/domain extraction; no model-assisted enrichment on NAS |
| vault_extract_project_mentions | read | enable on NAS | — |
| vault_curation_plan | read | plan-only / read-only only | Returns durable `plan_id`; apply blocked |
| vault_curation_apply | write | blocked pending approval | curation apply blocked; requires separate operator approval |
| vault_create_moc_plan | read | plan-only / read-only only | Applied only via `vault_curation_apply` (blocked) |
| vault_auto_link_plan | read | plan-only / read-only only | Applied only via `vault_curation_apply` (blocked) |
| vault_bulk_tagging_plan | read | plan-only / read-only only | Applied only via `vault_curation_apply` (blocked) |
| vault_email_to_note_plan | read | plan-only / read-only only | Apply counterpart blocked; preview only |
| vault_email_to_note_apply | write | blocked pending approval | email-to-note apply blocked; requires separate operator approval |
| search_sources | read | blocked pending approval | source-intelligence search blocked on NAS MCP |
| search_knowledge | read | blocked pending approval | source-intelligence mixed search blocked on NAS MCP |
| source_index_status | read | blocked pending approval | source-intelligence status blocked on NAS MCP |
| rebuild_source_index | write | blocked pending approval | source-intelligence index rebuild blocked on NAS MCP |
| generate_source_card | write | blocked pending approval | source-intelligence card generation blocked on NAS MCP |
| refresh_stale_source_notes | write | blocked pending approval | source-intelligence refresh blocked on NAS MCP |
| summarize_source | write | blocked pending approval | source-intelligence summarize blocked on NAS MCP |
| llm_chat_ingest | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_classify | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_summarize | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_extract_decisions | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_extract_action_items | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_select_template | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_link_existing_notes | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_to_note_plan | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_to_note_apply | write | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_update_topic_memory_plan | read | blocked pending approval | LLM chat memory tools blocked on NAS MCP |
| llm_chat_update_topic_memory_apply | write | blocked pending approval | LLM chat memory tools blocked on NAS MCP |

### Disposition summary

| Disposition | Count |
|-------------|------:|
| enable on NAS | 19 |
| enable with NAS guardrails | 4 |
| plan-only / read-only only | 9 |
| blocked pending approval | 24 |
| not applicable to NAS | 0 |
| **Total** | **56** |

## NAS_OBSIDIAN_BLOCKED reference

All keys in `NAS_OBSIDIAN_BLOCKED` (24 entries) are marked **blocked pending approval** above. `vault_semantic_search` appears in the blocked map and is listed separately in the disposition rules (not duplicated in the map count).

## Test coverage reference

17 `test_obsidian_mcp_*.py` files under `tests/`:

| Test file | Primary coverage area |
|-----------|----------------------|
| `tests/test_obsidian_mcp_backend.py` | MCP backend / service wiring |
| `tests/test_obsidian_mcp_config_forward_compat.py` | Config forward compatibility |
| `tests/test_obsidian_mcp_curation.py` | Curation plan/apply |
| `tests/test_obsidian_mcp_curation_ext.py` | Extended curation (MOC, auto-link, bulk tag, email-to-note) |
| `tests/test_obsidian_mcp_domain.py` | Construction/PM domain tools |
| `tests/test_obsidian_mcp_email.py` | EML read/inventory/parse |
| `tests/test_obsidian_mcp_fileops.py` | Move/rename/archive/delete plan+apply |
| `tests/test_obsidian_mcp_frontmatter.py` | Frontmatter read/update/search/dataview |
| `tests/test_obsidian_mcp_graph.py` | Backlinks, unlinked mentions, note graph |
| `tests/test_obsidian_mcp_llm_chat.py` | LLM chat memory tools |
| `tests/test_obsidian_mcp_oauth.py` | OAuth scopes (`_TOOL_SCOPES`) enforcement |
| `tests/test_obsidian_mcp_ollama_validation.py` | Ollama/summarization backend validation |
| `tests/test_obsidian_mcp_read_hardening.py` | Read path hardening |
| `tests/test_obsidian_mcp_search.py` | `search_vault`, semantic search |
| `tests/test_obsidian_mcp_summarize.py` | `vault_summarize_note` / `vault_summarize_folder` |
| `tests/test_obsidian_mcp_templates.py` | Template + daily note tools |
| `tests/test_obsidian_mcp_timeout.py` | Tool timeout behavior |

NAS-specific vault path and compose guards: `tests/test_nas_mcp_readonly.py` (`NAS_VAULT_HOST`, `NAS_VAULT_CONTAINER`, `test_compose_vault_mount_uses_nas_obsidian_path`, `test_mcp_config_vault_root_is_container_mount`).

## Source files

- `src/hb_assistant/obsidian_mcp/tools.py` — `_TOOL_REGISTRY` (56 tools)
- `src/hb_assistant/obsidian_mcp/mcp_app.py` — `_TOOL_SCOPES` (Mac OAuth read/write)
- `src/hb_assistant/nas_mcp/obsidian_adapter.py` — `NAS_OBSIDIAN_BLOCKED`, NAS dispatch handlers
- `src/hb_assistant/nas_mcp/config.py` — `NasObsidianConfig.vault_root` resolution
- `deploy/nas/mcp/compose-mcp.yaml` — host→container vault bind mount
- `deploy/nas/mcp/hb-pa-config.mcp.example.yml` — container vault root `/mnt/vault`
- `config/config.example.yml` — Mac example vault `~/Documents/Obsidian Vault`
