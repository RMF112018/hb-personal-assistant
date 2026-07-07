# N8C-18 — Feedback Capture and Review Loop Integration — Closeout

**Phase:** N8C-18 (bounded operator feedback on existing N8C artifacts → ADVISORY, operator-review-required
review-loop recommendations, in feedback-owned tables only)
**Status:** implemented + verified; **COMMITTED** locally (plain message, no AI trailer, no push).

## Commit lineage
- N8C-14 citation-safe drafts: `ae483f39`
- N8C-15 workflow routing: `a5441dab`
- N8C-16 live workflow MCP tools: `65ee1268`
- N8C-17 core workflow handlers (committed this session): `0eb3ccb4` — `feat(nas): add n8c core workflow handlers`
- N8C-18 branch: `ops/nas-second-brain-n8c-18-feedback-review-loop-20260707T201026Z`
- N8C-18 base commit: `0eb3ccb4`

## What N8C-18 delivers
A narrow, feedback-owned capture layer. An operator records bounded feedback on an EXISTING N8C artifact
(workflow result/section/artifact, answer draft, research packet/citation, source ref, review item, claim,
memory, decision, preference, open loop, advisory next step), and the service derives **deterministic,
ADVISORY, operator-review-required** review-loop recommendations. Nothing upstream is mutated: no review
disposition, no source/workflow/packet/draft/projection/context-pack/decision/preference/open-loop record.

- **Schema V109** — five feedback-owned tables (`assistant_feedback_records` / `_targets` /
  `_recommendations` / `_receipts` / `_events`). The fixed no-execution / feedback-only / advisory-review-loop
  policy is pinned by CHECK on both the record and the recommendation, and `requires_operator_review` is
  pinned to `1`. There is deliberately NO accept/reject/defer/dispose/executed/sent/scheduled column anywhere.
- **Deterministic identity** — `feedback_id` folds feedback type + sorted target signatures + bounded note +
  author + builder version, so resubmitting identical feedback dedupes (idempotent reuse).
- **Advisory derivation** — a conservative `feedback_type → recommendation_type` map (e.g. `wrong_source →
  suggest_source_check`, `duplicate → suggest_deduplicate`, `candidate_should_be_trusted →
  suggest_relabel_trusted`). `useful` yields no recommendation. Every recommendation is a SUGGESTION for the
  operator's review loop — never an applied relabel/accept/reject/defer/dispose.
- **Read/write surfaces** — a CLI writer (`feedback add`, default `--dry-run`, only `--apply` persists, into
  the five feedback tables only) plus read-only CLI (`list/show/recommendations/export`), read-only GET API
  routes, and six read-only remote MCP tools over a `mode=ro&immutable=1 + query_only=ON` snapshot.

## Changed files (additive set)
NEW:
- `src/hb_assistant/store/assistant_feedback_tables.py` — V109 DDL (5 tables + indexes, pinned policy CHECKs).
- `src/hb_assistant/obsidian_mcp/feedback_models.py` — deterministic ids, bounded caps, fixed policy block,
  advisory recommendation derivation.
- `src/hb_assistant/obsidian_mcp/feedback_repository.py` — sole reader/writer of the five feedback tables.
- `src/hb_assistant/obsidian_mcp/feedback_service.py` — `preview_feedback` / `capture_feedback(apply=)` /
  `export_feedback`.
- `src/hb_assistant/cli/feedback.py` — Typer app (`add`/`list`/`show`/`recommendations`/`export`).
- Tests: `test_feedback_v109_migration.py`, `test_feedback_models.py`, `test_feedback_repository.py`,
  `test_feedback_service.py`, `test_feedback_cli.py`, `test_fastapi_analytics_feedback.py`,
  `test_nas_mcp_feedback.py`.

MODIFIED:
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION = 109`; `_v109_statements()`; guarded V109
  apply block (`INSERT ... (109, 'v109_assistant_feedback', ?)`).
- `src/hb_assistant/cli/main.py` — register the `feedback` Typer group (alphabetical import).
- `src/hb_assistant/construction/analytics/api.py` — six read-only GET feedback routes.
- `src/hb_assistant/nas_mcp/profile.py` — `assistant_feedback_enabled()` + gate_status line.
- `src/hb_assistant/nas_mcp/broker.py` — `ASSISTANT_FEEDBACK_TOOLS`, status advert, gated dispatch branch,
  `_invoke_assistant_feedback` RO-snapshot handler.
- `src/hb_assistant/nas_mcp/tool_registration.py` — gated `@mcp.tool()` block for the six read-only tools.
- Schema-head tests made head-agnostic: `test_answer_draft_v108_migration.py`,
  `test_source_identity_v99_migration.py`, `test_nas_mcp_workflows.py`, `test_workflow_registry.py`.

## Boundaries preserved
No action staging (that is N8C-19 — NO `assistant_action*` table exists here). No execution / scheduler /
automation / external task / email / calendar / reminder / Slack. No review-disposition write. No mutation of
any upstream record. No live LLM/Qwen/Ollama, no `source_file_read` / `SourceContentProvider` / scan /
reindex / source-card generation, no external (Procore/Sage/Graph) sync. No raw prompt/response, no raw email
body, no full upstream payload copy — bounded ids + metadata only. `ai_outputs_card_upsert` remains the only
sanctioned remote write; the MCP finality guard is not weakened. No N8D `agent_bridge`, no
`construction/second_brain|email`, no source/card rendering touched. N8C-13 operator UI stays deferred.
