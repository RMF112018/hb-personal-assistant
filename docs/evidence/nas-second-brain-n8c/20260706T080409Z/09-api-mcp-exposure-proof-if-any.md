# API / MCP Exposure

Local API (read-only GET only), added inside `create_app` following the N8C-4 claim-route template:
- `GET /api/assistant/enrichment/jobs` (status/job_type/limit filters)
- `GET /api/assistant/enrichment/jobs/{job_id}` (404 if absent)
- `GET /api/assistant/enrichment/receipts`
All role-gated, guardrailed (`read_only: true`), bounded, no secret leakage. No write verbs exist on
this surface (POST/DELETE -> 404/405, proven).

Write API DEFERRED: queue/claim/complete/fail are driven only by the internal service +
`hb-assistant qwen-worker` CLI. A local write API is reserved behind a default-OFF, operator-only,
local/Tailnet-only flag `HB_ASSISTANT_ENRICHMENT_WORKER_API` for a later slice (absent when off).

Remote MCP: NO enrichment tool added. The remote surface is still exactly the 12 read-only
`assistant_*` nav tools (`test_registration_adds_12_assistant_tools_when_enabled` unchanged); no
`nas_mcp` module references the enrichment repository.
