# Source Intelligence Index + Indexed Search — Final Report (Foundation + Watcher)

Branch `feat/obsidian-mcp-source-intelligence` off `origin/main` `b122b536` (includes merged
timeout-guard PR #198). **Uncommitted**, pending Bobby's authorization.

## Why the architecture changed
Obsidian is now the **curated knowledge layer, not the raw document repository**. Raw files stay
in their working dirs; the app indexes their metadata/text/relationships into SQLite + FTS5 and
searches the index. This also removes the last broad-`search_vault` live-scan (which could still
hit `tool_timeout`): broad search is now index-backed.

## Scope delivered (this pass)
V93 index schema + FTS5; source indexer (operator rebuild + watchdog watcher with polling
fallback); Obsidian-note index; MCP tools `search_sources`/`search_knowledge`/`source_index_status`/
`rebuild_source_index`; broad `search_vault` switched to the index; API status + operator-rebuild
routes. **Deferred (next slices):** curated note generation, Ollama enrichment/embeddings, Settings UI.

## Schema (V93, additive, 92→93)
8 tables `source_intelligence_{sources,metadata,text,chunks,relationships,generated_notes,events,
state}` + 2 regular FTS5 tables (`source_intelligence_fts`, `obsidian_note_fts`, unified columns
`text_excerpt,rel_path,aux`). Invariants as DDL CHECKs (mirroring `email_messages.full_body_persisted`):
`_text`/`_chunks` `raw_body_persisted=0`, `redaction_applied=1`; every source is a file OR a domain
link (table CHECK); email = link-only (no `_text`). Repo-managed explicit FTS sync (no triggers);
`fts_rowid` stored in `_metadata`. FTS5 availability probed at migrate time → `_state.fts_available`.

## Behavior
- **No live scans in MCP requests.** Indexing runs off the request path: the watchdog watcher
  worker thread, and a bounded one-shot drain thread spawned by operator `rebuild_source_index`
  (works even with the watcher off). Durable queue (`_events`) survives restart; stuck `processing`
  re-queued by TTL. Idempotent on `(sha256, mtime_ns)`.
- **Broad `search_vault`**: small `path_scope` → live narrow scan (`live_scope_scan`); broad/no-scope
  → `obsidian_note_fts` (`note_index`); empty/stale/no-FTS → `{results:[]}` + structured index status
  (`index_unavailable`/`note_index_empty`) — never a recursive scan. Closure unchanged → timeout
  guard + scope preserved.
- **Reuse**: `files/parsers/{pdf,docx,xlsx}`, `HB_PROJECT_NUMBER_RE`, `pathsafe` ignore predicate,
  `security/text_vault` (sensitive roots store an encrypted ref + excerpt withheld from FTS).
- **Email policy preserved**: domain sources are LINK rows; bodies never re-ingested; CHECKs back it.

## Validation
- New tests: `test_migrator_v93_source_intelligence.py` (7), `test_source_index_repository.py` (9),
  `test_obsidian_source_index.py` (9), `test_obsidian_source_watch.py` (6) — incl. real watchdog
  event indexing, polling fallback, durable queue, caps, idempotency, delete reconcile, Text Vault.
- Extended `test_obsidian_mcp_backend.py` (42-tool list) + `test_obsidian_mcp_timeout.py` (4 new
  tools in the strict-JSON sweep; 42 passed).
- Suites: 62 passed (backend/oauth/migrator/repo/index/watch) + 42 (timeout) + 20 regression
  (read-hardening, data-quality inventory, v89 migrator, second-brain CLI). ruff clean on all new
  modules; mypy clean (7 modules). api.py carries 50 pre-existing ruff findings (zero added — stash
  comparison identical).
- **Runtime (real app lifespan + /mcp)**: status route 200; rebuild 403 (viewer) / 200 (operator);
  rebuild indexed external_file + obsidian_note; MCP search_sources→source_index,
  search_knowledge→both types, broad search_vault→note_index, source_index_status→fts True; all with
  tool_start/tool_end, 0 tracebacks/timeouts.

## Files
NEW: store/source_intelligence_tables.py; obsidian_mcp/{source_index_repository,source_indexer,
source_search,source_watch}.py; 4 test files. MODIFIED: store/migrator.py (V93), obsidian_mcp/
{config,service,tools,mcp_app}.py, construction/analytics/api.py, pyproject.toml (watch extra),
tests/{test_obsidian_mcp_backend,test_obsidian_mcp_timeout}.py.

## Security / guardrails
No raw email bodies (link-only + CHECKs); sensitive text → Text Vault ref, withheld from FTS; bounded
excerpts/snippets/chunks; no token/content in logs (allow-list redactor, `project_key` added, free-text
`query` dropped); operator-gated rebuild; configured-roots-only (abs paths, pathsafe + symlink guard);
additive migration; timeout guard + OAuth + write guardrails untouched.

## Remaining risks / follow-ups
- Project `key` resolution deferred (project_number from regex; canonical key = next slice).
- Note generation, Ollama enrichment/embeddings, Settings UI = explicit next slices.
- watchdog is an optional extra (installed in this venv); polling fallback covers its absence.
- The one-shot rebuild drain + watcher worker both open their own per-thread sqlite connections.

## Commit status
UNCOMMITTED on the feature branch. Intended 3-commit sequence (schema+repo / indexer+search+tools /
watcher) — pending Bobby's explicit authorization.
