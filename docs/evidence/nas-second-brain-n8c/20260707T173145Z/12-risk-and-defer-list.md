# 12 — Risks & deferrals

## Deferred (intentional)
- N8C-13 operator UI / command center — no branch, no code, no schema.
- N8C-16 live MCP/ChatGPT workflow consumption — no MCP tools added; local service contract first.
- N8C-17 full implementations of meeting_prep / daily_brief_context / project_intelligence_context /
  open_loop_triage — N8C-15 routes + marks deferred only.
- N8C-18 action staging — `action_draft_preparation` is contract-only.
- N8D agent_bridge — untouched, not imported.

## Watch items
- `source_file_lookup` routes to the source-connector target but does NOT execute a live search in the
  routing layer (config coupling deferred to N8C-17). The envelope names the target + echoes the
  bounded query/source_root_key; retrieval depth stays with the existing source-connector surface.
- api.py legacy ruff debt is 48 pre-existing errors; the N8C-15 GET block adds 0 new (verified).
- Router degrades to "absent" only on a *missing table* (unmigrated DB); any other DB error still
  propagates — this is deliberate graceful degradation, not error-swallowing.
- `tests/test_review_router.py` (unrelated construction/email wall-clock date flake) is OUT OF SCOPE —
  not run or modified this phase.
- MEMORY.md compaction remains deferred (approaching read limit); handled as a separate careful pass,
  not mixed into this deliverable.

## Uncommitted state
20-ish working-tree items (see 13-git-status). GitHub Desktop auto-stash could disrupt them; N8C-15 is
intentionally left uncommitted pending explicit commit authorization.
