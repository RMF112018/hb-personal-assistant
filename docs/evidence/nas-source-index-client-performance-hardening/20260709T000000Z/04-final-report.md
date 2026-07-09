# Final report — source index client performance hardening

1. **Branch:** ops/source-index-client-performance-hardening-20260709
2. **Base commit:** 4c510db65a4fe7409c80e810baf3fd17e316133d (origin/main)
3. **Final commit:** (see git log after commit)
4. **Worktree:** /Users/bobbyfetting/hb-personal-assistant-worktrees/ops/source-index-client-performance-hardening-20260709
5. **Schema migrations:** none (no V116)
6. **Tools added (canonical):** assistant_source_index_health, assistant_source_query_plan
7. **Tools modified:** structure service responses; connector search ranking/explanations/metadata; archive destination_state; vault path aliases; dataview FROM fail-closed; structure default-ON
8. **Aliases added:** assistant_output_* → pa_output_* (10 tools)
9. **Structure visibility:** Option A — source_structure **default-ON** (kill-switch =0)
10. **Canonical count:** 87 assistant tools / 14 groups (default exposed 87)
11. **Tests:** final-pytest.txt (focused suite green)
12. **Live MCP:** not run (no credentials); see 03-operator-connected-client-test-script.md
13. **Evidence:** this folder
14. **Already implemented on main:** V115 structure index, connector, zip validation, destructive preflight
15. **Implemented this work:** health, query plan, default-visible structure, ranking+explanations, project normalize, output aliases, archive state, vault path aliases, dataview FROM error, routing/manifest
16. **Skipped:** full structure incremental scanner; Ollama; full context-pack kinds (P2 — infrastructure exists, deferred to avoid surface churn); live connected-client retest
17. **Risks:** ranking is within-page re-rank over BM25; compact project numbers require path/query context; exposure tests must exclude assistant_output_* from canonical counts
18. **Next phase:** operator live client matrix; optional context-pack kinds; launchd structure rebuild
