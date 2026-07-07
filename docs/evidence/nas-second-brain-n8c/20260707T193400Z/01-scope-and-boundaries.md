# 01 — Scope, Clarifications, and Boundaries

N8C-17 was executed against Bobby's 13-point approval. Mapping of each clarification to the implementation:

1. **N8C-16 committed first** with explicit staged-only paths, plain message, no AI trailer, no push →
   `65ee1268`. See `13-git-status.md`.
2. **Schema-free.** `LATEST_SCHEMA_VERSION == 108`; `store/migrator.py` NOT edited. Proven in
   `tests/test_nas_mcp_workflows.py::test_no_schema_bump` + `git diff` (no migrator entry).
3. **Handlers only.** No new MCP tool, no rename, no new API route, no new CLI command, no persistence, no
   action staging/execution, no tasks/reminders/emails/calendar. `03-contract.md`, `07-boundaries.md`.
4. **Bounded copy.** `section_body` / `evidence_excerpt` / full exports / raw payload JSON / raw prompts /
   raw email bodies / `*_json` blobs are NEVER copied; only ids, statuses, titles/summaries, review labels,
   citation ids, source refs, root-relative paths, counts, timestamps, warnings, deferred markers.
   `06-artifact-policy.md`.
5. **Context, not new facts.** Handlers assemble bounded advisory summaries from already-bounded metadata;
   no new facts, no final answer/brief/memo/report. `workflow_policy="context_only"`. `06`, `07`.
6. **Bounded before AND after.** Every list accessor clamps its limit into `[1, MAX_ITEMS]` (`_bounded_limit`)
   and every section is capped (`MAX_SECTION_ITEMS`) — no whole-table load. `05-readonly.md`.
7. **Source-file = metadata/search/list only.** `project_intelligence_context` calls the INDEX search
   (`source_connector_service.search_source_files`) — never `source_file_read`, never `SourceContentProvider`,
   never a live filesystem read, scan, reindex, or source-card generation. The FTS snippet is dropped.
   `09-no-live-source-read.md`.
8. **Conservative classification.** accepted/operator-accepted → trusted; candidate/unreviewed/needs_review
   → candidate; rejected/not_required/superseded/stale → excluded; missing/unknown/contradictory → candidate
   (NEVER trusted). A review overlay wins over a record's own status. `06-artifact-policy.md`.
9. **Advisory-only next steps.** `advisory_next_steps` carries navigation/review guidance only — proven free
   of every execution verb (send/schedule/create task/remind/email/notify/assign/close/reopen/accept/reject/
   defer/dispose/launch/run/execute/build/apply/scan/reindex/create N8D). `07-boundaries.md`.
10. **Genuinely implemented.** `implementation_deferred_to` is now `N8C-18` (only action staging/delivery
    remains); no `build_*` deferred marker survives; results return non-empty `workflow_sections` when
    artifacts exist. `03-contract.md`, `11-tests.md`.
11. **Unchanged tool names, richer context.** `assistant_route_workflow` and `assistant_get_workflow_context`
    return `workflow_sections` for implemented workflows through the SAME names. Proven in
    `tests/test_nas_mcp_workflows.py`. `10-tool-inventory.md`.
12. **nas_mcp change authorized.** The only nas_mcp edit is the one additive read-only line in
    `_workflow_context_view` (workflow_sections/workflow_policy pass-through). Bobby explicitly authorized
    this exception via AskUserQuestion ("Add workflow_sections to view") to satisfy #11 without a new tool.
13. **All standing boundaries preserved** — see `00-closeout.md` and `07-boundaries.md`.
