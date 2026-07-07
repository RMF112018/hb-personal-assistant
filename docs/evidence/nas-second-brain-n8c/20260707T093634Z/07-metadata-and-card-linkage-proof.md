# 07 — Metadata & Original-vs-Card Linkage Proof

`source_file_metadata(source_id | source_ref)` returns, from `get_source_detail` + `list_cards_for_source`
(both read-only, `conn=`-threaded):

- identity: `object_type="source_file"`, `is_source_file=True`, `source_id`, `source_ref`, `source_root_key`,
  root-relative `rel_path`, `source_kind`, `extension`, `mime_type`;
- file metadata: `size_bytes`, `mtime_ns`, `content_digest` (= content_sha256), `page/paragraph/sheet_count`,
  `extraction_status`, `indexed_text_available`, `source_state` (active/deleted);
- **supplemental** card linkage: `generated_card_available`, `generated_card_rel_path`,
  `generated_card_status`, with an explicit note "supplemental artifact; the original source file is the
  primary object";
- bounded `neighbors` (up to 20 sibling source files in the same folder, each `{source_ref, rel_path,
  source_root_key}`) — advisory context, no absolute paths.

## Distinction (primary vs supplemental vs separate)
The ORIGINAL source file is the primary object. The generated source card is exposed ONLY as supplemental
metadata (never forced). Vault notes are a separate object type not returned here. A source with no card is
still returned as the primary object.

## Proof (all pass)
`test_source_connector_service.py`: `test_metadata_distinguishes_source_and_card` (attaches a card, asserts
primary-object shape + supplemental linkage; a card-less source is still primary),
`test_metadata_by_source_ref`, `test_metadata_unknown_raises` (`source_not_found`).
`test_fastapi_analytics_source_connector.py::test_metadata_and_read`.
