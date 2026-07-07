# 10 — No execution / no write-back / no persistence

- **No persistence:** schema head stays V108; `store/migrator.py` byte-unchanged; no workflow
  run/event/receipt/history table exists. `workflow_id` is an ephemeral deterministic response id
  (folded from router version + a digest of the bounded request), never written to the DB.
- **No write-back:** the router only calls repository READ methods; upstream packet/draft/projection/
  review/decision/memory/context-pack/source records are never mutated.
- **No execution:** every envelope carries `action_policy=no_execution` + `execution_policy=route_only`
  (`test_envelope_has_fixed_policies_and_is_bounded`). No email/calendar/task/reminder/Slack/N8D job is
  triggered. `action_draft_preparation` returns deferred capabilities only.
- **Bounded / no raw payloads:** `bounded_metadata` copies whitelisted scalars only and drops every
  `*_json`; `test_envelope_carries_no_raw_bodies_or_payloads` asserts no `_json`, `section_body`,
  `evidence_excerpt`, or `result_json` reaches the envelope. API responses secret-scan clean.
- **No N8D:** no `agent_bridge` import/edit; no bridge/run/orchestration tables.
