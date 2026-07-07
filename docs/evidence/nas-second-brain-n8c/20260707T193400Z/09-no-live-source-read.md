# 09 — No Live Source Read / No Build / No Scan-Reindex

## project_intelligence_context uses the INDEX only (clarification #7)
`project_intelligence_context` surfaces source FILES via `router._search_source_files`, which calls
`source_connector_service.search_source_files(SourceIndexRepository(db), ObsidianMcpConfig(), …)` — the
N8C-12 read-only FTS index surface. It:
- does NOT call `source_file_read`, NOR instantiate `SourceContentProvider`, NOR open any source file;
- does NOT perform a live filesystem read, scan, or reindex;
- does NOT generate a source card;
- returns bounded index metadata only (`_SOURCE_FILE_WL`) — the FTS `snippet` is dropped;
- degrades to `[]` when the index is absent/disabled or the query is blank (guarded), never a crash. Proven:
  `test_workflow_handlers.py::test_project_intelligence_source_files_absent_index_is_empty` +
  `test_source_files_carry_bounded_metadata_never_snippet`.

## No build / apply / writer
No handler builds an artifact. A missing explicitly-required artifact is REPORTED as
`missing_required_artifact` with a deferred marker — never constructed. Proven:
`test_workflow_handlers.py::test_open_loop_triage_explicit_missing_is_missing_required` and the AST guards in
`05-readonly-and-bounded.md` (no `build_answer_draft`/`build_research_packet`/`upsert_*`/`persist_*`).

## AST guard specifics (workflow_handlers.py)
`test_workflow_handlers.py::test_handlers_source_has_no_writer_or_source_read` asserts the parsed handler
module calls none of `{upsert_draft, upsert_packet, persist_pack, record_disposition, build_answer_draft,
build_research_packet, read_source_file, source_file_read, reindex, scan, list_source_files}` and imports
none of `{SourceContentProvider, answer_draft_builder, research_packet_builder}`.

## No external sync
No Procore/Sage/Microsoft-Graph call. `external_source_sync` is an honest deferred capability
(project_intelligence spec), not an action taken here.
