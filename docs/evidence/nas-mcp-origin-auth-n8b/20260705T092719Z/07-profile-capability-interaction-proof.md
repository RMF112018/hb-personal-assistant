# 07 — Profile / Capability Interaction Proof

**Authentication does not grant capability.** The foundation `remote_cloudflare` profile
remains the capability authority; origin auth only decides *whether the request is admitted
at all*. A valid token still cannot exceed the profile.

## Enforcement order in `broker.dispatch`
1. hard-denied tool names (`raw_sql`, `shell`, …) → deny.
2. `blocked_write_tools()` (profile) → deny — **before** any per-token consideration.
3. optional per-token `allowed_tools` narrowing → deny if tool not in the token's allow-list.
4. dispatch.

So the profile block (step 2) fires regardless of a valid token, and a token can only
*further restrict* (step 3), never broaden.

## Proven for `remote_cloudflare` + a valid `AuthContext`
| requirement | test | result |
|---|---|---|
| Tier-4 broad vault write (`create_note`) blocked | `test_valid_token_cannot_call_blocked_or_scratch_writes` | deny `write_tool_blocked_by_profile` |
| scratch output writer (`hb_output_write_file`) blocked | same | deny `write_tool_blocked_by_profile` |
| `ai_outputs_card_upsert` allowed | `test_valid_token_can_call_ai_outputs_but_not_outside_folder` | ok |
| write outside `AI Outputs` (traversal title) | same | nothing lands outside the `AI Outputs` folder |
| per-token allow-list narrows | `test_allowed_tools_narrowing` | `hb_mcp_status` ok, `hb_root_list` deny `tool_not_in_token_scope` |

Tier-5 (admin/destructive) tools are never registered in any profile — unchanged.
