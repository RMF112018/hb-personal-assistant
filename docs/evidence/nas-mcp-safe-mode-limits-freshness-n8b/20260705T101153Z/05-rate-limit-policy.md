# 05 — Rate Limit Policy

`limits.py` makes the existing per-call bounds env-overridable + operator-override-aware
(raise-only) and adds the net-new controls. All fail closed; none leak content.

## Scopes, env seams, enforcement
| scope | env | base (config) | enforced at |
|---|---|---|---|
| response_size | `HB_MCP_MAX_RESPONSE_BYTES` | max_response_bytes (256000) | `db_tools` (raise) |
| rows | `HB_MCP_MAX_ROWS` | max_db_rows (100) | `db_tools` (clamp) |
| file_excerpt | `HB_MCP_MAX_FILE_EXCERPT_BYTES` | max_excerpt_bytes (16384) | `fs_tools`/`file_readers` (clamp+truncate) |
| search_results | `HB_MCP_MAX_SEARCH_RESULTS` | max_search_results (50) | `fs_tools`/`root_tools` search clamp |
| card_size | `HB_MCP_MAX_CARD_BYTES` | max_card_bytes (262144) | `ai_outputs` (raise) |
| write_count | `HB_MCP_MAX_AI_OUTPUTS_WRITES_PER_WINDOW` | 20 / `HB_MCP_WRITE_WINDOW_SECONDS` 3600 | broker write-window |
| timeout | `HB_MCP_TOOL_TIMEOUT_SECONDS` | tool_timeout_seconds (30) | broker post-hoc flag (best-effort) |
| (concurrency) | `HB_MCP_MAX_CONCURRENT_CALLS` | max_concurrent_calls (8) | broker `ConcurrencyLimiter` |

`apply_effective_limits()` resolves size/row/search/card scopes into a per-request config copy
at the broker boundary, so the deep read/write paths honor env + override values automatically.

## Reuse, not duplication
Binary-dump denial, extension allowlists, denied-name/dir-segment, and traversal/symlink
guards are the existing `path_safe`/`fs_tools` mechanisms — reused, not reimplemented. The
dead `config.max_write_bytes` is left in place but noted; the effective card cap is
`max_card_bytes`.

## Timeout — best-effort (HOLD)
The NAS broker dispatches sync tools; a hard wall-clock pre-emption of arbitrary sync work is
not implemented (documented HOLD). The knob + a post-hoc `slow_tool` audit flag exist; real
work is bounded by the static per-call size/row caps, the response-byte cap, and the
concurrency cap. Fine-grained deadline injection into bounded loops is deferred.
