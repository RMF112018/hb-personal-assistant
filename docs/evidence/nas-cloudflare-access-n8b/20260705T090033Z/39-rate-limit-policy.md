# 39 — Rate-Limit Policy (+ operator override) — design/gap

## EXISTS today (per-call bounds, `nas_mcp/config.py:64-70`)
`max_excerpt_bytes=16384`, `max_list_entries=100`, `max_db_rows=100`, `default_db_rows=25`, `max_response_bytes=256000`, `max_write_bytes=262144`, `max_output_file_bytes=1048576`; obsidian side adds `tool_timeout_seconds=30`, search-result/snippet clamps, `external_source_scan_max_files`. AI Outputs body ≤ 256 KiB, title ≤ 120. Broad scans/binary dumps denied by root policy + extension allowlists.

## GAP (to implement in a later sub-phase)
No request-**rate**/QPS or concurrency throttle, and no long-job→job-id path (not needed for the current read+AI-Outputs-write scope). Design:
- Per-client (Access identity/service-token → `source_client`) token-bucket: max writes/window, max concurrent calls.
- Long-running ops (none in current scope) must return a job id, not hold the connection.

## Operator override (design; remote LLM cannot self-approve)
```
hb_mcp_override_create(scope, reason, expires_in_minutes, max_value, client, tool_name?)
```
- Narrow by scope/client/tool; **expires**; audit-logged; **local operator/admin approval only** (an OAuth/remote principal can never approve — mirror `obsidian_mcp` `_operator_mode` returning False for OAuth principals); emergency revoke.

## Verdict
Per-call bounds EXIST; rate/QPS + override = GAP for a later sub-phase (not a foundation blocker; the surface is read + one bounded write).
