# Repo-truth audit (clean worktree)

Base: 4c510db6 origin/main  
Branch: ops/source-index-client-performance-hardening-20260709  
Baseline pytest: passed (see 00-baseline-pytest.txt)

## Confirmed gaps to implement
1. Structure tools default-OFF → not client-visible for map
2. No unified assistant_source_index_health
3. No assistant_source_query_plan; search_route is partial
4. File search BM25-only; no match_explanation / multi-stage rank
5. Project number only hyphen full/partial; no compact/spaced/dotted normalize
6. pa_output_* only; no assistant_output_* aliases
7. Archive leaves destination_state stale
8. Preflight lacks map/health/refusal routes for structure/map
9. Client manifest two-tier only (no structure map tier)
10. No source tool telemetry envelope

## Already sufficient (no reimplementation)
V115 schema/ingest/service; connector list/search/read; zip validation; destructive preflight short-circuit; host path redaction patterns
