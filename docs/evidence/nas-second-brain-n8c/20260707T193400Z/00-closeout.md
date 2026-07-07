# N8C-17 — Core Workflow Context Handlers — Closeout

**Phase:** N8C-17 (Daily Brief, Meeting Prep, Project Intelligence, Open-Loop Triage — deterministic,
read-only workflow CONTEXT-assembly handlers over existing N8C artifacts)
**Status:** implemented + verified; **UNCOMMITTED** (stop-before-commit per authorization)

## Commit lineage
- N8C-14 citation-safe drafts: `ae483f39`
- N8C-15 workflow routing: `a5441dab`
- N8C-16 live workflow MCP tools (committed this session): `65ee1268` — `feat(nas): add n8c workflow mcp tools`
- N8C-17 branch: `ops/nas-second-brain-n8c-17-core-workflows-20260707T185750Z`
- N8C-17 base commit: `65ee1268`  ·  HEAD at close: still `65ee1268` (N8C-17 uncommitted)

## What N8C-17 delivers
The four "route + mark deferred" stubs in the N8C-15 router are replaced by genuine, deterministic,
read-only **context-assembly handlers**. Each turns a routed `WorkflowRequest` into named, bounded
`workflow_sections` drawn from EXISTING N8C read repositories — no execution, no persistence, no schema, no
new MCP tools, no live source-file read, no LLM.

- `daily_brief_context` — recent packs/projections/packets/drafts/decisions/preferences/open-loops/memory
  split into `trusted_updates` / `candidate_updates` / `open_loops` / `review_needed`.
- `meeting_prep` — supplied artifacts + prior decisions/preferences + open loops + `questions_to_resolve`
  (+ explicit-draft/packet citations). No agenda/invite/calendar/task.
- `project_intelligence_context` — `trusted_facts` / `candidate_findings` (claims + memory) + INDEXED
  source-FILE references (metadata only) + decisions/preferences + open loops + review-needed.
- `open_loop_triage` — `active` / `candidate` / `blocked_or_waiting` / `review_needed` /
  `stale_or_superseded` open loops + `related_decisions`. No task/reminder/disposition write.

The additive envelope fields `workflow_sections` (dict) and `workflow_policy="context_only"` are emitted for
all workflows and pass through the UNCHANGED N8C-16 MCP tools / CLI / API (no new tool, no rename, no route).

## Changed files
- `src/hb_assistant/obsidian_mcp/workflow_handlers.py` — **NEW.** The four `assemble_*` handlers + the
  conservative `_classify` + bounded section/label/source-ref collectors.
- `src/hb_assistant/obsidian_mcp/workflow_router.py` — four `_handle_*` delegate to the handlers; bounded
  guarded LIST accessors (`_list_context_packs/_list_projections/_list_research_packets/_list_drafts/
  _list_decisions/_list_preferences/_list_nodes/_list_review_items/_list_claims/_packet_citations/
  _search_source_files`); `_envelope` gains `workflow_sections`/`workflow_policy`; `_CLAIM_WL`/
  `_SOURCE_FILE_WL`; `_bounded_limit`/`_bound_sections`. Removed orphan `_route_deferred_context`.
- `src/hb_assistant/obsidian_mcp/workflow_models.py` — additive request fields (`since/until/priority/
  meeting_title/attendee_names/attendee_orgs/limit`) all bounded in `from_inputs`; `WORKFLOW_POLICY_
  CONTEXT_ONLY`; `MAX_ATTENDEES/MAX_SECTION_ITEMS/DEFAULT_ASSEMBLY_LIMIT`; `_clean_str_list`/`_clean_limit`.
- `src/hb_assistant/obsidian_mcp/workflow_registry.py` — the four specs `implementation_deferred_to="N8C-18"`
  (context implemented in N8C-17; only action staging/delivery remains); deferred_capabilities trimmed to
  `stage_*` gaps (no `build_*`); catalog notes updated.
- `src/hb_assistant/nas_mcp/broker.py` — **one authorized additive read-only change**: `_workflow_context_view`
  passes through `workflow_sections` + `workflow_policy` (SELECT-only; no new logic, no reads). Authorized by
  Bobby to reconcile clarification #11 (get_workflow_context must return workflow_sections) with #12.
- Tests: NEW `tests/test_workflow_handlers.py` (48 tests); updated `tests/test_workflow_router.py`,
  `tests/test_workflow_registry.py`, `tests/test_nas_mcp_workflows.py`.

## Boundaries preserved (unchanged)
Schema stays **V108** (`store/migrator.py` untouched). No new MCP tool / no rename / no API route / no CLI
command / no persistence / no action staging / no execution / no tasks-reminders-emails-calendar / no live
LLM/Qwen/Ollama / no build/apply writer / no source scan/reindex / no source-card generation / no
`source_file_read` / no live source read / no external (Procore/Sage/Graph) sync / no raw prompt/response /
no raw email body / no full upstream payload copy. `ai_outputs_card_upsert` remains the only sanctioned
remote write. No N8D `agent_bridge`, no `construction/second_brain|email`, no source/card rendering touched.

## Deferred (unchanged)
N8C-13 operator UI (no branch). N8C-18 action staging / delivery (the four workflows' `stage_*`
capabilities). N8D `agent_bridge` — untouched, not imported.
