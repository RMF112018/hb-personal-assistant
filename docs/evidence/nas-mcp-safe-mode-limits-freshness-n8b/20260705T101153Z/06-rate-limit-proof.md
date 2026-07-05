# 06 — Rate Limit Proof

| control | test | result |
|---|---|---|
| rows capped by env | `test_rows_capped_by_env` | `HB_MCP_MAX_ROWS=2` → hb_db_select returns ≤ 2 rows |
| search results capped | `test_search_results_capped_by_env` | `HB_MCP_MAX_SEARCH_RESULTS=2` → match_count ≤ 2 |
| oversized card denied | `test_oversized_card_denied` | `HB_MCP_MAX_CARD_BYTES=16` → `body_too_large` |
| binary dump denied | `test_binary_and_broad_scan_denied` | excerpt of a binary file → deny |
| broad scan / traversal denied | same | `../../etc/passwd` → deny |
| concurrency cap | `test_concurrency_limiter_unit` | 3rd acquire over cap=2 → False; releases free a slot |

Each limit denial returns a structured error and is audited; no content is echoed in the error.
