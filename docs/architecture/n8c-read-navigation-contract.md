# N8C-3 — Read/Navigation Contract (API · MCP · Frontend)

Stable request/response contract for the read-only source/card/note navigation surface introduced in
N8C-3. One shared service (`hb_assistant/obsidian_mcp/source_navigation.py`) backs three consumers:

- **Local API** — `GET /api/assistant/*` on the analytics FastAPI shell (vite-proxied to `127.0.0.1`).
- **Remote MCP** — `assistant_*` tools on the NAS MCP surface (Cloudflare tunnel).
- **Frontend** — thin `getAssistant*` wrappers in `frontend/src/lib/api.ts` + the read-only
  `AssistantPage`.

All three return the **same response shapes** (below). The API additionally wraps each payload in a
`"guardrails"` block.

## Content & safety posture

- **Read-only.** No endpoint/tool writes. The MCP tools serve from a read-only DB snapshot
  (`mode=ro&immutable=1` + `PRAGMA query_only=ON`, threaded via `conn=`, no live-DB fallback); the API
  reads the live DB with SELECTs only. `ai_outputs_card_upsert` remains the ONLY sanctioned remote
  write; raw SQL / shell / absolute-path reads stay denied.
- **Complete, unredacted content** (operator-authorized). No PII masking; `assistant_get_vault_note`
  returns the whole note (bounded only by a high absolute ceiling, ~2,000,000 chars, for tunnel
  stability). Search `snippet` fields are FTS previews for discovery, not redactions — use
  `get_vault_note` / `get_source` for full content.
- **Relative paths only.** Structural path fields (`path` / `note_rel_path` / `source_rel_path`) are
  always vault-/root-relative plus `source_root_key`. Absolute NAS mount paths are never returned in a
  structural field.
- **Bounded.** List responses always carry `count`, `limit` (clamped ≤ 100), `truncated`.
- **Auth.** Remote MCP requires origin auth (hard-on in `remote_cloudflare`). Local API is all-roles
  read-only (`X-HB-UI-Role` accepted; no role gating on these routes). Kill switch:
  `HB_MCP_ASSISTANT_NAV=0` (default on).

## Endpoints ↔ MCP tools ↔ shapes

| API (all GET) | MCP tool | Response (plus `guardrails` on API) |
|---|---|---|
| `/api/assistant/sources?q=&limit=&project_key=` | `assistant_search_sources` | `{sources:[{result_type,source_id,path,project_key,score,snippet}], count, limit, truncated}` |
| `/api/assistant/sources/{source_id}` | `assistant_get_source` | `{source:{source_id,source_kind,source_root_key,rel_path,…,text_excerpt}, card, is_duplicate, active_card_paths}` · 404 if absent |
| `/api/assistant/sources/{source_id}/card` | `assistant_get_card_for_source` | `{source_id, card, is_duplicate, active_card_paths}` |
| `/api/assistant/sources/{source_id}/state` | `assistant_get_card_state` | `{source_id, state, card_paths, reason, legacy_flags}` — `state` ∈ current/stale/missing/duplicate/source_deleted/no_card |
| `/api/assistant/sources/{source_id}/related` | `assistant_get_related_sources` | `{source_id, related:[{dst_kind,dst_ref,relation,confidence,evidence,dst_rel_path}], count}` |
| `/api/assistant/cards/search?q=&limit=&path_prefix=` | `assistant_search_cards` | `{cards:[{result_type,source_id,path,tags,score,snippet}], count, limit, truncated}` |
| `/api/assistant/card-source?note_rel_path=` | `assistant_get_source_for_card` | `{note_rel_path, resolution, source_id, sources, count}` — `resolution` ∈ none/unique/ambiguous; `source_id` set only when unique (never guesses) |
| `/api/assistant/cards/stale?limit=` | `assistant_list_stale_cards` | `{stale_cards:[{source_id,note_rel_path}], count, limit, truncated}` |
| `/api/assistant/cards/duplicates?limit=` | `assistant_list_duplicate_cards` | `{duplicate_cards:[{source_id,active_card_paths,card_count}], count, limit, truncated}` |
| `/api/assistant/cards/ambiguous?limit=` | `assistant_list_ambiguous_card_links` | `{ambiguous_card_links:[{note_rel_path,source_ids,source_count}], count, limit, truncated}` |
| `/api/assistant/recent-changes?limit=&event_types=` | `assistant_recent_changes` | `{changes:[{event_id,source_id,rel_path,source_root_key,event_type,status,created_at}], count, limit, truncated}` |
| `/api/assistant/vault-note?note_rel_path=&max_chars=` | `assistant_get_vault_note` | `{path, file_type, content, metadata:{truncated,…}, note_type}` · 400 on absolute/traversal/NUL/protected/symlink-escape |

## Errors

- **404** — unknown `source_id` (`get_source`).
- **400** — unsafe vault path for `vault-note`: absolute, `..` traversal, NUL byte, protected/hidden
  folder (`.git`/`.obsidian`/`.trash`/`.venv`/`.smart-env`/`.hb-assistant` or any dotfile), symlink
  escaping the vault. (MCP surfaces the same as a deny.)
- **`assistant_nav_disabled`** — returned when `HB_MCP_ASSISTANT_NAV=0`.

## Frontend client

`frontend/src/lib/api.ts` exports 12 flat `getAssistant*` wrappers (also on the `api` object), each a
`fetchJson('/api/assistant/…')` GET that auto-injects `X-HB-UI-Role`. `AssistantPage` is a read-only
browser (source search + recent changes + stale cards) — no write actions. Later slices (N8C-9+) can
add richer views against this same contract without backend changes.
