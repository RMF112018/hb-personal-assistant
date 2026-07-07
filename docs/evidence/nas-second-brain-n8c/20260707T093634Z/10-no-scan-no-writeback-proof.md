# 10 — No-Scan / No-Writeback / No-Raw-Path / No-Raw-SQL Proof

## No live recursive scan in the request path
Search/list read indexed rows only (FTS / indexed `source_intelligence_sources`). The bounded read opens
EXACTLY ONE configured file. `test_source_connector_service.py::test_read_no_directory_traversal` installs a
spy over `os.scandir` and `os.walk` and asserts **zero** calls across `read` + `search` + `list`.

## No writeback / no mutation
All repo access is read-only queries (`get_source_detail`, `search_source_files`, `list_source_files`,
`count_source_files`, `index_status`, `list_cards_for_source`) threaded through a read-only connection. MCP
uses `_ro_uri` (`mode=ro&immutable=1`) + `PRAGMA query_only=ON` (UPDATE raises `OperationalError` —
`test_nas_mcp_source_connector::test_snapshot_is_read_only`). `test_reads_do_not_mutate` hashes the source /
metadata / text / generated_notes / events tables and asserts the digest is UNCHANGED across
status/search/list/metadata/read.

## No scan/reindex, no card generation
No connector path calls `scan_source_root`, `rebuild_source_index`, or any card generator. No such route/tool
exists (verified by the forbidden-verb assert in `test_nas_mcp_source_connector` — none of the 48 assistant
tools contain scan/reindex/rebuild/generate/build/write/…).

## No raw SQL exposure
The broker's `DENIED_TOOL_NAMES` (`raw_sql`/`sql`/`shell`/`exec`/…) is unchanged; the connector exposes only
structured read tools. No arbitrary-SQL surface added.

## No absolute host paths
Every search/list/metadata/read payload carries root-relative `rel_path` + `source_root_key` only.
`source_status` drops the raw `configured_roots` state blob (which can carry absolute paths). Tests JSON-dump
each payload and assert the temp root abs path and `/Users/` never appear
(`_no_abs` / `_assert_safe`).
