# 02 — Source-Root Access Audit Carry-Forward (summary; audit zip NOT committed)

The external repo-truth audit's relevant findings (summarized here; the audit zip is intentionally NOT
committed) and how N8C-12 resolves each:

| Audit finding | Resolution in N8C-12 |
|---|---|
| Live NAS MCP exposes many vault/note tools; behaves like a vault connector | Adds a dedicated source-FILE connector tool family `assistant_source_*` with client-facing descriptions that route source-file questions to them (see `04`, `11`). |
| Generic `hb_root_search` lists one dir, filters immediate entry NAMES only, non-recursive, hard-capped, no cursor | Left unchanged (not broadened — proven by `test_nas_mcp_source_connector::test_hb_root_tools_not_broadened`). Index-backed search/list added instead. |
| `search_sources` / `search_knowledge` / `source_index_status` blocked in the live NAS adapter | Kept blocked (`NAS_OBSIDIAN_BLOCKED` intact). Exposed the same underlying index reads through NEW dedicated read-only `assistant_source_*` tools over the RO snapshot — not by unblocking the raw obsidian tools. |
| Index records already root-scoped via `source_root_key` + `rel_path` | Reused directly; no schema change. |
| Existing source-search rows do NOT expose `source_root_key` → ambiguous follow-up | New `search_source_files` / `list_source_files` repo reads ALWAYS return `source_root_key` + an opaque `source_ref` (see `05`). |
| Source-root scanning should stay outside the MCP request path | Search/list read indexed rows only; the bounded read opens exactly one configured file (no walk/scan) — proven by a traversal spy (`10`). |
| Generated source cards should be supplemental, not the only path to originals | Metadata marks the original file primary and the generated card supplemental; `file_read` reads the original (bounded), never forcing a card (see `07`, `08`). |

No secrets, absolute private paths, or raw private content are reproduced from the audit here.
