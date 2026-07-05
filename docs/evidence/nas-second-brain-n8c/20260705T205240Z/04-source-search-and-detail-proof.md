# 04 — Source Search & Detail Proof

## Covered by
`tests/test_obsidian_source_navigation.py`:
- `test_search_sources_bounded_envelope` — `search_sources("unique_token_zzz")` returns the indexed
  source; envelope has `sources/count/limit/truncated`; `count == len(sources) <= limit`; **no
  absolute private-root path appears anywhere in the payload** (`_no_absolute_paths`).
- `test_search_cards_bounded` — `search_cards("alpha")` returns the bounded card envelope.
- `test_limit_is_clamped` — `limit=10_000` clamps to `MAX_LIMIT` (100); negative limit clamps to ≥ 1.
- `test_get_source_detail_relative_only` — `get_source(sid)` returns `source.rel_path` (relative),
  `source_root_key="proj"`, primary `card`, `is_duplicate=False`; asserts neither the private source
  root nor the vault absolute path leaks.
- `test_get_source_missing_is_none` — unknown source_id → `None` (API maps to 404; MCP to a deny).

## Result
All pass. Search results and source detail carry relative paths only; bounding + clamping enforced.
