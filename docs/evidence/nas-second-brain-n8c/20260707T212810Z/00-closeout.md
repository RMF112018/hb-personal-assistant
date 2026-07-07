# N8C-19 — Action Staging, Not Action Execution — Closeout

**Phase:** N8C-19 (durable, source-backed, operator-review-required staging of proposed follow-up CANDIDATES
over the N8C-17 workflow context + N8C-18 advisory feedback — no execution)
**Status:** implemented + verified; **UNCOMMITTED** (stop-before-commit per authorization).

## Commit lineage
- N8C-16 live workflow MCP tools: `65ee1268`
- N8C-17 core workflow handlers (committed this session): `0eb3ccb4`
- N8C-18 feedback review loop (committed this session): `c2022562` — `feat(nas): add n8c feedback review loop`
- N8C-19 branch: `ops/nas-second-brain-n8c-19-action-staging-20260707T210017Z`
- N8C-19 base commit: `c2022562`  ·  HEAD at close: still `c2022562` (N8C-19 UNCOMMITTED)

## What N8C-19 delivers
A stage-owned layer that turns the read-only N8C-17 workflow CONTEXT envelope + N8C-18 ADVISORY feedback
recommendations into a bounded set of proposed follow-up CANDIDATES for operator review. **Staging is not
execution:** every staged item is pinned to `execution_status='not_executed'` / `external_system='none'` /
`external_ref=None` / `requires_operator_review=1`, and `staged_state` is only `candidate` or `blocked`.

- **Schema V110** — five stage-owned tables (`assistant_action_stages` / `_stage_items` / `_stage_citations`
  / `_stage_receipts` / `_stage_events`). The fixed no-execution / staged-only / staging-only /
  preserve-review-state policy is pinned by CHECK on the stage; each item's non-execution fields are pinned by
  CHECK. There is deliberately NO sent/scheduled/completed/executed/dispatched/emailed/n8d_job column.
- **Deterministic identity** — `stage_id` folds a `request_digest` (stage_type + workflow + policy + budget)
  and a `source_context_digest` (the ordered staged-item signatures), so a rebuild with unchanged context
  dedupes (idempotent), and a changed context supersedes the prior stage of the same lineage.
- **Deterministic section → candidate mapping** — open_loops → open_loop_follow_up; review_needed →
  review_candidate; risks_or_caveats → project_risk_review; questions_to_resolve → information_gap_review;
  prior/related decisions → decision_review; known_preferences → preference_review; source_files →
  source_review. Trusted/context sections are established knowledge (skipped). Terminal sections
  (stale_or_superseded, excluded_items) stage `blocked` only.
- **Advisory-only gate** — each `advisory_next_steps` entry stages `human_follow_up`, UNLESS it reads like an
  execution instruction (send/email/schedule/create-task/…), which stages `blocked` with
  `block_reason='execution_like_advisory'` — never active.
- **Feedback integration** — each N8C-18 advisory recommendation stages as an advisory review candidate,
  anchored to its feedback lineage (read-only; the feedback record is never mutated).
- **Read/write surfaces** — a CLI writer (`action-stage build`, default `--dry-run`, only `--apply` persists,
  into the five stage tables only) + read-only CLI (`preview/list/show/export`), read-only GET API routes, and
  six read-only remote MCP tools over a `mode=ro&immutable=1 + query_only=ON` snapshot.

## Changed files (additive set)
NEW: `store/assistant_action_stage_tables.py`, `obsidian_mcp/action_stage_{models,repository,builder}.py`,
`cli/action_stage.py`; tests `test_action_stage_{v110_migration,models,repository,builder,cli}.py`,
`test_fastapi_analytics_action_stages.py`, `test_nas_mcp_action_stages.py`.
MODIFIED: `store/migrator.py` (`LATEST_SCHEMA_VERSION=110` + `_v110_statements()` + guarded V110 block);
`cli/main.py` (register `action-stage`); `construction/analytics/api.py` (six GET routes); `nas_mcp/profile.py`
(`assistant_action_stages_enabled()` + gate_status); `nas_mcp/broker.py` (`ASSISTANT_ACTION_STAGE_TOOLS` +
dispatch + RO handler); `nas_mcp/tool_registration.py` (six read-only tools); `tests/test_feedback_v109_
migration.py` (reframed `test_no_action_stage_tables` → head-agnostic `test_v109_statements_create_no_action_
stage_tables`, since V110 legitimately adds those tables at a higher schema version).

## Boundaries preserved
No execution / scheduler / automation / external task / email / calendar / reminder / Slack. No external
system (`external_system` pinned to `none`, `external_ref` pinned NULL by CHECK). No review-disposition write.
No mutation of any upstream record (workflow/feedback/review/source/draft/packet/projection/context-pack/
decision/preference/open-loop — all read-only inputs). No live LLM/Qwen/Ollama, no `source_file_read` /
`SourceContentProvider` / scan / reindex / source-card generation, no external sync. No raw prompt/response,
no raw email body, no full upstream payload copy. `ai_outputs_card_upsert` remains the only sanctioned remote
write; the MCP finality guard is not weakened. No N8D `agent_bridge`, no `construction/second_brain|email`, no
source/card rendering touched. N8C-13 operator UI stays deferred.
