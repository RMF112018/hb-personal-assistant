# 06 — Deferred-capabilities proof

- `action_draft_preparation` is CONTRACT-ONLY → `status=deferred`, `selected_artifacts=[]`,
  `deferred_capabilities=[stage_action_draft, prepare_action_object]`, deferred to **N8C-18**. No
  action / email draft / agenda / task / reminder / calendar item / staged action object is created
  (`test_action_draft_preparation_deferred_only`, `test_route_action_draft_preparation_deferred`).
- meeting_prep / daily_brief_context / project_intelligence_context / open_loop_triage route to
  targets but carry `implementation_deferred_to=N8C-17` + a `build_*` deferred capability
  (`test_context_workflows_marked_deferred_to_n8c17`, `test_daily_brief_and_project_context_mark_deferred`).
- A required-but-absent artifact → `status=missing_required_artifact` + deferred capability; the router
  never builds it (`test_missing_required_artifact_not_built`).
- Catalog notes: live consumption → N8C-16, operator UI → N8C-13, action staging → N8C-18.
