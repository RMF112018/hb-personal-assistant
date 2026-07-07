# 10 — Tool Inventory Delta

## New remote MCP tools (read-only), gated by `HB_MCP_ASSISTANT_FEEDBACK` (default-ON)
| tool | reads | write? |
| --- | --- | --- |
| `assistant_list_feedback` | records (filter type/status/workflow_id, bounded limit) | no |
| `assistant_get_feedback` | one record | no |
| `assistant_get_feedback_targets` | targets for a record | no |
| `assistant_get_feedback_recommendations` | advisory recommendations (filter type) | no |
| `assistant_get_feedback_summary` | bounded aggregate | no |
| `assistant_get_feedback_export` | `feedback_export_v1` (bounded) | no |

Count = 6. All over `mode=ro&immutable=1 + PRAGMA query_only=ON`. No write/capture/accept/stage MCP tool.

## New CLI commands (`hb-assistant feedback`)
`add` (write gate `--dry-run/--apply`, default dry-run), `list`, `show`, `recommendations`, `export`.

## New API routes (GET-only)
`/api/assistant/feedback`, `/summary`, `/recommendations`, `/{feedback_id}`, `/{feedback_id}/targets`,
`/{feedback_id}/export`.

## Unchanged
`ai_outputs_card_upsert` remains the only sanctioned remote write. No existing tool renamed or removed. All
prior assistant tool sets (nav / context-pack / memory / decision-memory / review / intelligence /
research-packet / source-connector / answer-draft / workflow) preserved BY NAME
(`test_nas_mcp_feedback.py::test_no_write_build_or_disposition_tool_registered`).
