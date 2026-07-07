# 09 — No live source read proof

`source_file_lookup` routes to the `source_connector` TARGET and echoes bounded query/source_root_key —
it performs no live filesystem read, OCR, scan/reindex, or source-card generation. The router's
source-connector path is target-naming only (retrieval depth deferred to N8C-17). Proven by
`test_source_lookup_routes_without_live_read` (primary_target == source_connector, no content) and the
AST guard excluding `read_source_file` / `SourceContentProvider` from the handler + views.
