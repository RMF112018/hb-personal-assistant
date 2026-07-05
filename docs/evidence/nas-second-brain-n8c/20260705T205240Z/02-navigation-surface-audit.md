# 02 — Navigation Surface Audit & Intentional Default-Content Policy

Per clarification #2, the NAS MCP exposure policy was inspected before adding any `assistant_*` tool,
so the default content posture is a **deliberate operator decision** on the record — not an accident.

## Prior default (for reference)
Before N8C-3 the remote surface returned no source-intelligence **row content**: the `hb_db_select`
allowlist (`nas_mcp/db_allowlist.py`) contained only `schema_migrations`, `NAS_OBSIDIAN_BLOCKED`
(`nas_mcp/obsidian_adapter.py`) blocked the source-intelligence search/status tools, and
`nas_mcp/freshness.py` exposed only aggregate counts/timestamps. That prior default was designed for a
generic internet surface, not for Bobby's own authenticated assistant.

## Intentional N8C-3 default (operator decision)
**Bobby intentionally approved the default authenticated remote MCP behavior as navigation PLUS bounded
deep content access.** The whole point of the Personal Intelligence Operating Layer is to chat with his
own data and files; a metadata/excerpt-only default would defeat that. So the authenticated remote
default is, by design:

- navigation access (search, listings, recent changes, related);
- source/card lookup and source↔card linkage;
- stale / duplicate / ambiguous / missing state access;
- **bounded deep source/card/vault-note content access** (complete, unredacted);
- relative paths only; read-only; no raw SQL; no arbitrary filesystem access; no shell/exec; no new
  write path; no raw/import DB mutation; no unauthenticated access.

This is not a reversal to roll back; it is the chosen policy for this surface.

## Trust boundary (defense in depth — all retained)
Deep content is deep **by default but still tool-mediated and bounded**. The trust boundary is:
- **Cloudflare / OAuth authentication** at the edge;
- **origin auth** (hard-on and un-overridable in `remote_cloudflare`, `profile.origin_auth_required()`)
  — no unauthenticated path;
- **MCP tool policy** — fixed `assistant_*` tools only; `DENIED_TOOL_NAMES`
  (raw_sql/sql/shell/exec/read_file_absolute/hb_output_delete) stay denied; no broad `db_allowlist`
  expansion (still only `schema_migrations`);
- **read-only snapshot DB** (`mode=ro&immutable=1` + `PRAGMA query_only=ON`, threaded via `conn=`, no
  live-DB fallback);
- **path-safe vault access** (absolute/traversal/NUL/protected-hidden/symlink-escape all rejected;
  raw `.eml` not exposed);
- **bounded result caps** (list limits clamped ≤ 100; content ceiling ~2,000,000 chars);
- **no new remote write surface** — `ai_outputs_card_upsert` remains the ONLY sanctioned write.

## Content policy detail
PII is not masked and content reads are not truncated for normal documents — that is the intended
"useful deep content," not a gap. If a future need arises, existing secret redaction (if any) is
preserved; N8C-3 does not add a broad redaction layer that would destroy normal personal/work content
utility. Access is deep, tool-mediated, bounded, authenticated, and read-only. Kill switch:
`HB_MCP_ASSISTANT_NAV=0`; rotate tokens on suspected leak.
