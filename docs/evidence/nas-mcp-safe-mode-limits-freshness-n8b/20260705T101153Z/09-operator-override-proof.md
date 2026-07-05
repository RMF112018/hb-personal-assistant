# 09 — Operator Override Proof

| requirement | test | result |
|---|---|---|
| remote/tool cannot create override | `test_no_mcp_tool_can_create_override` | broker dispatch of override_create/create_override/hb_override_create → not registered (ok:false) |
| operator CLI creates + revokes | `test_operator_cli_creates_and_revokes` | create returns record (scope/reason/revoked:false); revoke → `{revoked:true}` |
| reason + expiry required | `test_override_requires_reason_and_expiry` | blank reason and 0 expiry both raise OverrideError |
| extends only its scope | `test_override_extends_only_its_scope` | search_results→999; rows unchanged (base 100, no override) |
| raise-only (never lowers) | `test_raise_only_override_never_lowers` | override max_value=1 below base 100 → base wins |
| active override in status | `test_active_override_in_capability_mode` | `hb_capability_mode.active_override_count == 1` + scope shown |

The CLI `create` also writes an audit receipt (override_id + scope + client + reason + expiry) to
the NAS audit log when using the configured store.
