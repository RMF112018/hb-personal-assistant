# 12 — Risks & deferrals

## Deferred (intentional)
- N8C-13 operator UI / command center — no branch, no code, no schema.
- N8C-17 full workflow implementations (meeting_prep / daily_brief_context / project_intelligence_context /
  open_loop_triage) + source-connector retrieval depth.
- N8C-18 action staging — `action_draft_preparation` stays deferred-only through the MCP surface.
- N8D `agent_bridge` — untouched, not imported.

## Watch items
- The six MCP tools are internet-exposed (Cloudflare). Mitigated: default-ON kill switch
  `HB_MCP_ASSISTANT_WORKFLOWS`, read-only snapshot (`mode=ro&immutable=1` + `PRAGMA query_only=ON`), no
  write/build/apply/answer/action tool, no answer-verb tool name, origin auth still applies. Watch: keep
  the finality guard intact if any tool is ever renamed.
- Tool count is asserted as a +6 set-difference DELTA, not an absolute — resilient to unrelated repo
  changes. Observed before/after = 54 → 60.
- MCP-only change: no CLI/API expansion; N8C-15 CLI/API behavior preserved (no files touched there).
- `tests/test_review_router.py` (unrelated construction/email date flake) OUT OF SCOPE — not run/modified.
- MEMORY.md compaction remains deferred (approaching read limit); a dedicated careful pass, not mixed in.

## Uncommitted state
4 working-tree items (3 modified nas_mcp + 1 new test) + evidence dir. N8C-16 left uncommitted pending
explicit commit authorization. GitHub Desktop auto-stash could disrupt them.
