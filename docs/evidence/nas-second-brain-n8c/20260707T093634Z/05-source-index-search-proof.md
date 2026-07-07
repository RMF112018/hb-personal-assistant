# 05 — Source-Index Search + Result-Shape Proof

## Root-aware rows + stable source_ref
New additive repo read `search_source_files` (in `source_index_repository.py`) FTS-joins
`source_intelligence_fts` → metadata → sources and ALWAYS returns `source_root_key`, `rel_path`, `source_id`,
`file_ext`, bm25 `score`, bounded `snippet`. The service shapes each row with
`shape_source_file(...)` → `{source_id, source_ref, source_root_key, rel_path, source_kind, extension,
mime_type, snippet}`. The existing N8C-3 `search_sources` (which omitted `source_root_key`) is left untouched.

## Opaque, path-free source_ref (Bobby-confirmed contract)
`encode_source_ref(source_id)` → `hbsrc1_` + base64url(`source_id` + version-bound checksum).
- `source_id` is a sha256, so the ref carries NO rel_path / root key / filename / absolute path in reversible
  plaintext.
- `decode_source_ref` validates prefix + version-bound checksum server-side and raises on any tampering;
  metadata/read accept `source_id` OR `source_ref`.

## Filters + bounded snippets
`search_source_files` supports `source_root_key` and `file_ext` filters (bound params, no interpolation);
snippets bounded to `MAX_SNIPPET_CHARS = 240`.

## Proof
`test_source_connector_service.py`: `test_search_root_aware_rows`, `test_search_root_and_ext_filter`,
`test_search_bounded_snippet`, `test_status_and_roots_no_abs_paths`;
`test_fastapi_analytics_source_connector.py::test_search_is_root_aware`. All pass.
