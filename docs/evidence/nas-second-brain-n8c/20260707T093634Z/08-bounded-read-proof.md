# 08 — Bounded Original-Source Read Proof

`SourceContentProvider.read(source_id, *, max_chars, prefer_live)` — a narrow, single-file bounded reader.
Given a `source_id` it resolves EXACTLY ONE configured file and returns a bounded excerpt; it never walks,
globs, recurses, scans a root, refreshes an index, generates a card, or mutates anything.

## Safety order (any failure → indexed excerpt, never an error/leak)
1. source must exist in the index (`get_source_detail`; else `source_not_found`);
2. `prefer_live=False` → indexed excerpt (`reason=indexed_requested`);
3. deleted source → indexed (`source_deleted`);
4. `source_root_key` must map to an `enabled` configured root (else `root_unavailable`);
5. **sensitive roots are NEVER live-read** — no existing policy grants it → indexed (`sensitive_root`);
6. rel_path safe-path rules (`pathsafe.path_blocked` / `has_protected_segment`) → indexed (`blocked_path`);
7. extension in `config.allowed_file_types` ∩ supported text/parser exts (else denied `unsupported_type`);
8. containment: `abs_path.resolve()` must stay under `Path(root.path).resolve()` (else `path_escape`); no
   symlink escaping the root (`symlink_escape`);
9. file exists + within `config.max_file_mb` (else `file_absent`/`file_too_large`);
10. single `open` via the SAME deterministic `source_indexer._extract` used at index time (no new OCR); the
    extractor is asked for `max_chars+1` so `truncated` is exact; output bounded to `max_chars`.

Content is labelled `content_source`: `live_extract` or `indexed_excerpt_fallback`. Absolute host paths are
NEVER returned; full raw files are never dumped (`READ_MAX_CHARS = 20000`).

## Proof (all pass)
`test_source_connector_service.py`: `test_read_live_bounded` (bounded to max_chars, truncated flag),
`test_read_indexed_fallback_when_not_live`, `test_read_sensitive_root_never_live` (reason `sensitive_root`),
`test_read_denies_unsupported_binary` (png → denied, no content), `test_read_path_escape_is_contained`
(`../` rel_path → never a live read outside root), `test_read_no_directory_traversal` (traversal spy: zero
`os.scandir`/`os.walk` during read/search/list). `test_fastapi_analytics_source_connector.py::test_metadata_and_read`.
