# 00 — N8C-3 Closeout (Read/Navigation APIs, MCP Tools, Smoke View)

**Slice:** N8C-3 — Purpose-Built Read/Navigation APIs and MCP Tools.
**Branch:** `ops/nas-second-brain-n8c-03-read-navigation-20260705T205240Z`, base **`319ceff0`** (the
local N8C-2 commit). **Not committed, not pushed** — awaiting explicit authorization.

## What shipped
One shared **read-only** navigation service consumed by three surfaces:
1. **Service** — `src/hb_assistant/obsidian_mcp/source_navigation.py` (wraps N8C-2 identity + repo
   read primitives; every fn threads `conn=`; relative paths only; complete/unredacted content).
2. **Local API** — 12 `GET /api/assistant/*` routes on the analytics FastAPI shell.
3. **Remote MCP** — 12 `assistant_*` tools on the NAS MCP surface, served from a read-only DB snapshot.
4. **Frontend** — 12 `getAssistant*` client wrappers + read-only `AssistantPage` smoke view.
Plus one new read-only repo primitive (`list_recent_events`) and the contract doc
`docs/architecture/n8c-read-navigation-contract.md`.

## Intentional default policy: navigation + bounded deep content (see 02)
Bobby **intentionally approved** the default authenticated remote MCP behavior as navigation **plus
bounded deep content access** — the Personal Intelligence Operating Layer exists to chat with his own
data and files, so a metadata/excerpt-only default would defeat the purpose. This is a deliberate
operator decision, not a reversal to roll back. Deep content stays tool-mediated and bounded: read-only,
RO snapshot (`query_only`, no live-DB fallback), relative paths only, path-safe vault access, bounded
caps, mandatory origin auth, no raw SQL/shell/filesystem, no broad `db_allowlist` expansion, and
`ai_outputs_card_upsert` remains the ONLY sanctioned write.

## Verification (see 12)
44 new tests pass (18 service + 8 API + 12 MCP + 6 frontend). 98-test backend regression sweep green.
Ruff clean on all changed files. `LATEST_SCHEMA_VERSION` = 99 (no migration). `source_notes.py`
untouched (card rendering byte-unchanged). Obsidian tool count unchanged (56); `assistant_*` adds 12.

## Status
Complete and verified locally. **No commit. No push.** Awaiting authorization.
