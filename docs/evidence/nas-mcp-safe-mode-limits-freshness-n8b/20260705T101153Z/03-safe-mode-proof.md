# 03 — Safe Mode Proof

Under `remote_cloudflare` + `HB_MCP_SAFE_MODE=1`:

| requirement | test | result |
|---|---|---|
| status + freshness allowed | `test_safe_mode_allows_status_and_freshness` | `hb_mcp_status`, `hb_data_freshness` ok; `hb_capability_mode.safe_mode == true` |
| AI Outputs write denied | `test_safe_mode_denies_ai_outputs_and_mutations` | deny `safe_mode_active:ai_outputs_card_upsert` |
| broad vault write denied (before profile gate) | same | deny `safe_mode_active:create_note` |
| safe mode visible in status | `test_safe_mode_allows_status_and_freshness` | `exposure_profile.safe_mode == true` |
| origin auth still required | see `16` (freshness requires auth) | safe mode adds no unauthenticated path |

Default-off is proven by every other test in the suite running without `HB_MCP_SAFE_MODE` and
still allowing AI Outputs writes.
