# Future: MCP Query/Index Hardening (Phase 10L-G)

**Status: NOT implemented in Phase 10L.** This document scopes structured MCP query surfaces so external
/ cloud LLM agents can retrieve source-card intelligence without crawling vault folders. Phase 10L
(A+B+C) added no MCP tools.

## Target tools / resources

`hb_obsidian_search_cards`, `hb_obsidian_get_card`, `hb_obsidian_project_cards`,
`hb_obsidian_recent_changes`, `hb_obsidian_duplicate_groups`, `hb_obsidian_graph_neighbors`,
`hb_obsidian_email_thread_cards`, `hb_obsidian_cards_needing_review`, `hb_obsidian_summary_status`.

These build on the existing DB-backed index (`source_index_repository.py`, the `source_intelligence_*`
tables + `source_intelligence_fts` / `obsidian_note_fts`) and the `source_search.py` helpers — never a
filesystem crawl.

## Minimum filters

```json
{
  "project_key": "tropical", "project_number": "23-435-01",
  "document_type": ["rfi", "submittal", "schedule", "email", "attachment"],
  "domain": "work", "tags": ["source/type/rfi", "related/schedule"],
  "updated_after": "2026-07-01T00:00:00Z",
  "summary_status": "generated|pending|failed",
  "review_status": "needs_review|approved|rejected",
  "duplicate_status": "canonical|duplicate|none",
  "limit": 25
}
```

## Response posture

- Metadata-first, compact by default; card body only when explicitly requested.
- DB-backed index preferred over filesystem crawl.
- Sensitive fields (raw source paths, identifiers) omitted from the default response; exposed only under
  an explicit local/operator mode.

## Dependencies

`duplicate_status` / duplicate-group queries depend on the duplicate-collapse grouping layer
(see `future-source-update-history-and-duplicate-collapse.md`); `review_status` depends on the dynamic
classifier's `review_required` output (see `future-dynamic-classifier.md`).

## Explicitly out of scope for Phase 10L

No MCP tools, resources, or query filters are added in Phase 10L.
