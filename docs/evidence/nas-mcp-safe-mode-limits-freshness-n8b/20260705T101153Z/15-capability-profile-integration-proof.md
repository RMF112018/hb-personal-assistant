# 15 — Capability / Profile Integration Proof

The new controls respect `remote_cloudflare`; nothing weakens it.

| requirement | test / mechanism | result |
|---|---|---|
| freshness/status = Tier 0 | `test_freshness_tier0_in_audit` + `_capability_tier` | audit `capability_tier == 0` |
| override create not remotely available | `test_no_mcp_tool_can_create_override` | no dispatch path mints one |
| override status read-only allowed | `test_active_override_in_capability_mode` | `hb_capability_mode` shows count/scope |
| AI Outputs stays Tier 3, blocked by safe mode | `test_safe_mode_denies_ai_outputs_and_mutations` | tier 3 + `safe_mode_active` |
| Tier 4/5 stay blocked | inherited profile gates (foundation) + `_capability_tier` | broad writes tier 4 blocked |
| valid token never bypasses profile | inherited (origin-auth `07`) + safe/limit order | profile gate before dispatch |
| per-token allowed_tools only narrows | `test_per_token_allowed_tools_cannot_reach_freshness` | token scoped to hb_mcp_status → `tool_not_in_token_scope` on hb_data_freshness |

Enforcement order in `broker.dispatch`: hard-denied → safe-mode → profile blocked_write_tools →
per-token narrowing → write-window → concurrency → dispatch(effective limits) → release.
