# N8C-8 — no-action / no-writeback proof

## No action execution (dedicated proof)
N8C-8 records are advisory memory only. **No execution path of any kind was added.** Grep across the
entire N8C-8 change set (models / repository / extractor / CLI / API / MCP / schema) finds NO import or
call to email, calendar, task-system, Slack/Teams, notification, reminder, scheduler, subprocess/agent,
or HTTP-send functionality. The extractor's public surface is exactly:
`discover_decision_memory` · `preview_decision_memory` · `apply_decision_memory` · `export_decision_memory`
· `mark_open_loop_stale_if_needed` — all of which only read the N8C substrate and (only under `apply`)
write rows into the four N8C-8 tables. There is no "send", "run", "dispatch", "notify", "schedule", or
"execute" verb anywhere in the layer, and the 6 MCP tools are list/get only
(`test_nas_mcp_decision_memory.py::test_no_write_or_action_tool_registered` asserts no tool name contains
extract/apply/write/create/delete/persist/upsert/close/reopen/accept/reject/mark/send/remind).

## No writeback outside the four N8C-8 tables
- `preview` / `--dry-run`: every watched non-N8C-8 row count unchanged
  (`test_preview_and_dry_run_are_read_only`; CLI smoke).
- `--apply`: only `assistant_decision_records` / `_preference_records` / `_open_loop_records` /
  `_decision_memory_events` grow; claim / enrichment / context-pack / memory / source tables unchanged
  (`test_apply_writes_only_n8c8_tables`; CLI smoke).
- Candidate claims stay `candidate`/`unreviewed`; memory node status unchanged (`active`).

## No raw persistence
- Records store bounded `evidence_excerpt` (hard cap 2 000) + digests (`source_digest`/`card_digest`) +
  ids (`claim_id`/`receipt_id`/`compilation_id`/…) — never the enrichment `result_json`, a raw
  source/email body, or a raw prompt/response. Text caps: `*_text` 500, `normalized_*` 300.
- `export_decision_memory` emits JSON only; smoke export contained no `result_json`, no `/Users/`
  absolute path (`test_export_is_bounded_json_no_raw`).

## No vault / rendering / startup / N8D
- No vault write, no source/card rendering change (DB-only). No startup extractor/scheduler/watcher/
  worker — the four tables ship empty and only an explicit `extract --apply` writes.
- No `src/hb_assistant/agent_bridge/` in the worktree; no `agent_bridge` import in any changed file. No
  bridge job tables / execution envelopes / run orchestration / escalation gates. No vector store /
  LlamaIndex. No remote MCP write/action tools.
