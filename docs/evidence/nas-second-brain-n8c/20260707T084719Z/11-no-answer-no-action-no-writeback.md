# 11 — No-Answer / No-Action / No-Writeback

## No final answer
No `final_answer` / `answer_text` / `generated_answer` / `response` field in models or builder (grep: only
docstring lines asserting absence, research_packet_models.py:9,12). The answer-context contract is guidance
metadata only (see 04) and is never treated as answer content.

## No action execution
No email / calendar / task / reminder / notification / bridge integration. `answer_contract.action_policy =
"no_execution"` (models.py:244). No N8D import, no `agent_bridge` touch. `open_loops_policy = "advisory_only"`;
`implementation_research_context` items stay advisory (`implementation_note`/`open_question`), never
executable.

## No writeback
Builder + repository write only the 5 `assistant_research_packet*` tables (see 09). No mutation of
projection / review / source-advisory / vault / source-card-render / raw-import tables. No raw prompt/response
or email-body persistence. No full upstream payload copy — only bounded title/summary/excerpt + ids / digests
/ state / role.

## No autonomy
No startup builder / scheduler / watcher / worker. Build/apply is CLI-initiated only. No remote MCP
build/apply/answer/action tool.

Proof: `test_research_packet_builder.py` (no-final-answer-field, no-full-payload-copy assertions),
`test_nas_mcp_research_packets.py` (no write/build/answer/action tool; `ai_outputs_card_upsert` only write).
