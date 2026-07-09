# Final report — source index client performance hardening

1. **Branch:** ops/source-index-client-performance-hardening-20260709
2. **Base commit:** 4c510db65a4fe7409c80e810baf3fd17e316133d (origin/main)
3. **Final commit (implementation):** `6f54bdd017cdb51f6002322b6386f2752324e401`  
   **Docs evidence commit:** `d8dfa5ee4b2044999f2c1cb181f0abfbdc08f89a`  
   **Closeout HEAD:** see `05-final-head-and-inventory.md` (authoritative tip after reconciliation commit)
4. **Worktree:** /Users/bobbyfetting/hb-personal-assistant-worktrees/ops/source-index-client-performance-hardening-20260709
5. **Schema migrations:** none (no V116)
6. **Tools added (canonical):** assistant_source_index_health, assistant_source_query_plan
7. **Tools modified:** structure service responses; connector search ranking/explanations/metadata; archive destination_state; vault path aliases; dataview FROM fail-closed; structure default-ON
8. **Aliases added:** assistant_output_* → pa_output_* (10 tools)
9. **Structure visibility:** Option A — source_structure **default-ON** (kill-switch =0)
10. **Canonical count:** 87 assistant tools / 14 groups (default exposed 87)
11. **Tests:** `05-final-pytest-command.txt` + `05-final-pytest-with-command.txt` (exit 0); also `final-pytest.txt`
12. **Live MCP:** host health 200; authenticated /mcp 401 (origin auth required, no bearer in session). Client-style discovery + offline prompt matrix completed — see `05-mcp-client-discovery.json.txt`, `05-offline-prompt-matrix.json.txt`, `03-operator-connected-client-test-script.md`
13. **Evidence:** this folder
14. **Already implemented on main:** V115 structure index, connector, zip validation, destructive preflight
15. **Implemented this work:** health, query plan, default-visible structure, ranking+explanations, project normalize, output aliases, archive state, vault path aliases, dataview FROM error, routing/manifest
16. **Skipped:** full structure incremental scanner; Ollama; full context-pack kinds (P2 — infrastructure exists, deferred to avoid surface churn); live connected-client retest
17. **Risks:** ranking is within-page re-rank over BM25; compact project numbers require path/query context; exposure tests must exclude assistant_output_* from canonical counts
18. **Next phase:** operator live client matrix; optional context-pack kinds; launchd structure rebuild


## HEAD note

Report field historically pointed only at `6f54bdd0` (implementation). Branch tip later included
`d8dfa5ee` (docs hash record) and this closeout reconciliation commit. Use `05-final-head-and-inventory.md`
for the authoritative tip hash.
