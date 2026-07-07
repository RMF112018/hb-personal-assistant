# 04 — No Execution / No External System

## Pinned at the schema level
Every staged item row is pinned by CHECK to `execution_status='not_executed'`, `external_system='none'`,
`external_ref IS NULL`, `requires_operator_review=1`, and `staged_state ∈ {candidate, blocked}`. The stage
header is pinned to `action_policy='no_execution'` / `execution_policy='staged_only'` /
`workflow_policy='staging_only'`. A row physically cannot claim an execution, an external delivery, or an
active state.

## Pinned in the models (defense-in-depth)
`ActionStageItem.to_row()` always emits `execution_status='not_executed'`, `external_system='none'`,
`external_ref=None`, `requires_operator_review=1`, and validates `action_kind` / `staged_state` against the
schema enums. The action-kind vocabulary contains only internal-review kinds (no send/email/schedule/dispatch).

## Proven read-only / no-mutation
- `test_action_stage_builder::test_build_apply_persists_non_executing_items` — every persisted item is
  not_executed / external_system=none / external_ref=None / requires_operator_review=1 / candidate|blocked.
- `test_action_stage_builder::test_apply_mutates_no_upstream_table` and
  `test_action_stage_repository::test_upsert_writes_only_stage_tables` — snapshot every non-stage table's
  rowcount before/after apply; unchanged.
- `test_action_stage_repository::test_repository_only_writes_stage_tables` (static) — every INSERT/UPDATE/
  DELETE literal targets an `assistant_action_stage*` table.

## No execution/external/LLM symbols in source
`test_action_stage_builder::test_no_execution_external_or_llm_symbols_in_source` (comments + string literals
stripped via tokenize) asserts NONE of subprocess / os.system / smtplib / sendmail / send_email /
requests.post / httpx.post / urllib.request / ollama / openai / anthropic / agent_bridge /
SourceContentProvider / source_file_read / reindex / calendar / reminder appear in any stage module.
`test_modules_define_no_execution_entrypoint` — no function name implies execute/dispatch/send/schedule/
deliver/remind.
