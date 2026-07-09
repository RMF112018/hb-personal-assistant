# Final report — source index client performance hardening

1. **Branch:** `ops/source-index-client-performance-hardening-20260709`
2. **Base commit:** `4c510db65a4fe7409c80e810baf3fd17e316133d` (origin/main at branch create)
3. **Commits:**
   - **Implementation:** `6f54bdd017cdb51f6002322b6386f2752324e401`
   - **Docs hash record:** `d8dfa5ee4b2044999f2c1cb181f0abfbdc08f89a`
   - **Closeout evidence pack:** `b695f3c81ad9d65b3c2cc96a5614e560a4b5a66f`
   - **Authoritative tip (re-stamp if needed):** see `05-final-head-and-inventory.md` / current `git rev-parse HEAD` (`21d1aa55eedb524839e59557998ebd88ff954125` at last stamp generation)
4. **Worktree:** `/Users/bobbyfetting/hb-personal-assistant-worktrees/ops/source-index-client-performance-hardening-20260709`
5. **Schema migrations:** none (no V116)
6. **Tools added (canonical):** `assistant_source_index_health`, `assistant_source_query_plan`
7. **Tools modified:** structure service responses; connector search ranking/explanations/metadata; archive `destination_state`; vault path aliases; dataview FROM fail-closed; structure default-ON; project-map preflight triggers
8. **Aliases added:** `assistant_output_*` → `pa_output_*` (10 tools)
9. **Structure visibility:** Option A — `source_structure` **default-ON** (kill-switch `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0`)
10. **Canonical count:** 87 assistant tools / 14 groups (default exposed 87)
11. **Tests:** `05-final-pytest-command.txt` + `05-final-pytest-with-command.txt` (exit 0)
12. **Live MCP:** host health **200**; authenticated `/mcp` **401** (origin auth required). Client-style discovery + offline prompt matrix completed — `05-mcp-client-discovery.json.txt`, `05-offline-prompt-matrix.json.txt`, `05-live-nas-mcp-probe.md`
13. **Evidence:** `docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/`
14. **Already implemented on main:** V115 structure index, connector, zip validation, destructive preflight
15. **Implemented this work:** health, query plan, default-visible structure, ranking+explanations, project normalize, output aliases, archive state, vault path aliases, dataview FROM error, routing/manifest, closeout evidence
16. **Skipped / pending:** full structure incremental scanner; Ollama; full context-pack kinds (P2); **authenticated live connected-client matrix**
17. **Risks:** ranking is within-page re-rank over BM25; compact project numbers require path/query context; hosted surface still requires origin bearer
18. **Next phase:** operator live client matrix with origin auth; optional context-pack kinds; launchd structure rebuild

## HEAD note

Do not treat `6f54bdd0` alone as the branch tip. Use **`git rev-parse HEAD`** / `05-final-head-and-inventory.md`.

## Push / PR gate

No push/PR until live matrix runs **or** operator explicitly accepts pending live validation.
