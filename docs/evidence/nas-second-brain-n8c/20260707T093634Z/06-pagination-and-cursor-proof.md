# 06 — Deterministic Keyset Cursor Proof

## Contract
Every search/list response carries `items, count, limit, limit_applied, has_more, next_cursor, cursor, order,
truncated` (`page_envelope`). No offset pagination.

## Keyset design
- **Cursor** = base64url(JSON `{v, qd, order, after}`), opaque. `qd = compute_query_digest({op, query,
  filters, order})` binds the cursor to its exact query/filter/order; `decode_cursor` raises
  `cursor_query_mismatch` if the request's digest or order differs.
- **Search** order = `bm25 rank` ascending (best first), tie-broken by `(source_root_key, rel_path,
  source_id)` — a total order even for equal-rank rows. The `after` tuple is `[rank, source_root_key,
  rel_path, source_id]`; the bm25 float round-trips exactly through JSON. The repo fetches `limit+1` and uses
  a keyset `WHERE rank > ? OR (rank = ? AND src_root > ?) OR …` continuation (no offset).
- **List** order = `(source_root_key, rel_path, source_id)`; `after` = `[rel_path, source_id]`, keyset
  continuation `WHERE rel_path > ? OR (rel_path = ? AND source_id > ?)`.
- No silent truncation: `truncated`/`has_more` are true iff a next page exists (from the limit+1 fetch);
  `next_cursor` is minted only then.

## Proof (all pass)
`test_source_connector_service.py`: `test_cursor_deterministic_nonoverlapping` (pages don't overlap),
`test_cursor_equal_rank_rows` (two identical-content files → identical bm25 rank still totally ordered, both
returned once), `test_cursor_query_mismatch_rejected`, `test_list_root_scoped_prefix_keyset`.
`test_fastapi_analytics_source_connector.py::test_search_cursor_round_trips` +
`test_bounded_limit_is_clamped` (limit clamped ≤ 100).
