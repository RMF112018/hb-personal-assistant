# 07 — No-build / no-apply / no-worker proof

`tests/test_workflow_router.py::test_router_calls_no_writer_or_worker` parses the router with `ast`
and asserts NONE of these appear as called attributes: upsert_draft/upsert_packet/upsert_projection,
persist_pack/persist_compilation, record_disposition, mark_*_stale*, build_answer_draft,
build_research_packet, read_source_file, reindex, scan. It also asserts the router never imports
`SourceContentProvider`, `answer_draft_builder`, or `research_packet_builder`.

The router therefore calls only repository READ methods — no build/apply writer, no source
scan/reindex, no source-card generation, no enrichment/qwen worker, no live source-file read. There is
no LLM/Qwen/Ollama/network dependency anywhere in the layer.
