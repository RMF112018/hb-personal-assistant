# 08 — Tool Inventory Delta

## New remote MCP tools (read-only), gated by `HB_MCP_ASSISTANT_ACTION_STAGES` (default-ON)
| tool | reads | write? |
| --- | --- | --- |
| `assistant_list_action_stages` | stages (filter type/status/workflow_type, bounded limit) | no |
| `assistant_get_action_stage` | one stage header | no |
| `assistant_get_action_stage_items` | staged items (filter staged_state) | no |
| `assistant_get_action_stage_citations` | provenance citations | no |
| `assistant_get_action_stage_summary` | bounded aggregate | no |
| `assistant_get_action_stage_export` | `action_stage_export_v1` (bounded) | no |

Count = 6. All over `mode=ro&immutable=1 + PRAGMA query_only=ON`. No stage-write/build/apply/execute MCP tool.

## New CLI commands (`hb-assistant action-stage`)
`preview` (RO), `build` (write gate `--dry-run/--apply`, default dry-run), `list`, `show`, `export`.

## New API routes (GET-only)
`/api/assistant/action-stages`, `/summary`, `/{stage_id}`, `/{stage_id}/items`, `/{stage_id}/citations`,
`/{stage_id}/export`.

## Unchanged
`ai_outputs_card_upsert` remains the only sanctioned remote write. No existing tool renamed or removed. All
prior assistant tool sets (nav / … / research-packet / answer-draft / workflow / feedback) preserved BY NAME
(`test_nas_mcp_action_stages::test_no_write_build_or_execute_tool_registered`).
