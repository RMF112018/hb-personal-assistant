# 13 — Risk / Defer List & Git Status

## Deferred (with rationale)
1. **Full external-source-file body retrieval** — `get_source` returns DB detail + the stored bounded
   excerpt (the DB physically stores only a bounded excerpt: `raw_body_persisted=0`). Complete content
   of the ORIGINAL non-vault source file (e.g. a PDF under a Work root) is served for **vault** notes
   via `assistant_get_vault_note`; reading original non-vault files in full would reuse the existing
   `hb_root_read_*` path-safety and is left to a follow-up (`assistant_get_source_content`). Not a
   redaction — a scope boundary.
2. **Reverse-lookup / recent-events indexes** — `list_recent_events` scans `source_intelligence_events`
   (idx `(status, created_at)` exists; a bare `created_at` index is not added — a migration). Acceptable
   at current volume.
3. **Richer frontend views** — only a minimal read-only smoke page shipped (clarification #6). Source
   detail / card-state / vault-note viewers are left to N8C-9+ on the same contract.

## Out of scope for N8C-3 (later slices)
No Qwen queue; no claim/decision/open-loop tables; no context packs; no maintenance loops; no
research/feedback surfaces; no broad graph schema; no schema migration (`LATEST_SCHEMA_VERSION` = 99);
no raw SQL / arbitrary filesystem exposure; no new remote **write** path (`ai_outputs_card_upsert`
stays the only sanctioned write); no raw/import DB mutation; no mass card migration/rewrite.

## Intentional default policy (on record, not a risk to roll back)
Navigation + **bounded deep content access** on the authenticated remote surface is Bobby's deliberate
operator decision (see `02-navigation-surface-audit.md`) — the intended behavior, not a reversal. The
trust boundary is Cloudflare/OAuth auth + origin auth + MCP tool policy + read-only snapshot DB
(`query_only`, no live-DB fallback) + path-safe vault access + bounded result caps + denied raw
SQL/shell/arbitrary-filesystem tools + no new remote write surface. Kill switch
`HB_MCP_ASSISTANT_NAV=0`; rotate tokens on suspected leak. No broad `db_allowlist` expansion; no
raw/import DB mutation; no schema migration.

## Stop-condition check — none tripped
No write surface added; RO snapshot proven (`query_only`); no schema migration; no raw/import DB
mutation; denied SQL/shell/fs still denied; existing `hb_*` tools + obsidian count (56) unchanged;
identity/ambiguity/stale/duplicate proven read-only; evidence carries no secrets/raw-emails/private
paths. The only posture change (remote content exposure) was explicitly operator-authorized.

## Git status
- **Branch:** `ops/nas-second-brain-n8c-03-read-navigation-20260705T205240Z`
- **Base:** `319ceff0` (verified ancestor of HEAD) — the local N8C-2 commit. N8C-1/N8C-2/N8C-3 are all
  local-only.
- **Not committed, not pushed.** Commit only after explicit authorization; no push without authorization.

### `git status --short`
```
 M frontend/src/app/routes.tsx
 M frontend/src/lib/api.ts
 M frontend/src/navigation/navigationModel.ts
 M src/hb_assistant/construction/analytics/api.py
 M src/hb_assistant/nas_mcp/broker.py
 M src/hb_assistant/nas_mcp/profile.py
 M src/hb_assistant/nas_mcp/tool_registration.py
 M src/hb_assistant/obsidian_mcp/source_index_repository.py
?? docs/architecture/n8c-read-navigation-contract.md
?? docs/evidence/nas-second-brain-n8c/20260705T205240Z/
?? frontend/src/lib/assistantApi.test.ts
?? frontend/src/pages/AssistantPage.test.tsx
?? frontend/src/pages/AssistantPage.tsx
?? src/hb_assistant/obsidian_mcp/source_navigation.py
?? tests/test_fastapi_analytics_assistant_nav.py
?? tests/test_nas_mcp_assistant_nav.py
?? tests/test_obsidian_source_navigation.py
```

### Tracked diffstat vs `319ceff0`
8 files changed, 577 insertions(+), 3 deletions(-) (api.py +117, api.ts +259, broker.py +93,
tool_registration.py +66, source_index_repository.py +24, routes.tsx +6, profile.py +13,
navigationModel.ts +2). Plus new: `source_navigation.py`, 3 backend test files, 2 frontend test files,
`AssistantPage.tsx`, the contract doc, and this evidence bundle.
