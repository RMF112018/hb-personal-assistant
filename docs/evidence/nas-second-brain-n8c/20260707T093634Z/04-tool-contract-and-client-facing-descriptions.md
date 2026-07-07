# 04 — Tool Contract & Client-Facing Descriptions

## Naming (repo-consistent, Bobby-confirmed)
Prefix `assistant_source_*` (consistent with the 42 existing `assistant_*` tools, the broker tuples,
`hb_mcp_status` `assistant_*` filtering, `_invoke_assistant_*` dispatch, and by-name test asserts).
Kill-switch `HB_MCP_ASSISTANT_SOURCE_CONNECTOR` (default-ON, independent).

## The 6 tools (all read-only)
| Tool | Purpose |
|---|---|
| `assistant_source_status` | source-index status + configured source-root summary |
| `assistant_source_roots_list` | configured source roots (key/enabled/sensitive + file counts) |
| `assistant_source_files_list` | index-backed listing under a root/prefix, cursor-paged |
| `assistant_source_file_search` | root-aware FTS over indexed source-file content, cursor-paged |
| `assistant_source_file_metadata` | metadata by source_id/source_ref; original-vs-card distinction |
| `assistant_source_file_read` | bounded, extension-gated single-file read (indexed fallback) |

## Client-facing descriptions distinguish object types
Each registered description explicitly routes source-FILE questions to these tools and away from vault notes /
generated cards, e.g. `assistant_source_file_search`:

> "Use when the user asks to find files in NAS source folders / project folders / documents — PDFs,
> contracts, invoices, drawings, proposals, spreadsheets. … NOT for Obsidian vault notes."

and `assistant_source_file_read`: "read an original source file's content — not a vault note or source card."

The existing N8C-3 nav tools (`assistant_search_sources`/`assistant_search_cards`/`assistant_get_vault_note`)
carry NO docstrings — thin descriptions that contributed to the source-file mismatch. N8C-12's tools ship
rich, disambiguating descriptions (proven in `11`).
