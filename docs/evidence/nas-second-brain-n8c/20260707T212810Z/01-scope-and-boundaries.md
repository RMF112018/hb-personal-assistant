# 01 — Scope and Boundaries

## In scope (N8C-19)
- Durable, source-backed staging of proposed follow-up CANDIDATES derived from the N8C-17 workflow CONTEXT
  envelope (read-only) + N8C-18 ADVISORY feedback recommendations (read-only).
- Stage-owned V110 schema (5 tables) + models + repository (idempotent + lineage supersede) + builder + CLI
  writer + read-only API + six read-only remote MCP tools.
- Every staged item is a candidate/blocked follow-up pinned to not_executed / external_system=none /
  external_ref=None / requires_operator_review=1.

## Explicitly OUT of scope (deferred / forbidden)
| Concern | Status |
| --- | --- |
| Action EXECUTION (running/sending/dispatching anything) | Forbidden — staging only |
| External system integration (email/calendar/Slack/task/reminder/N8D) | Forbidden — external_system pinned `none`, external_ref pinned NULL |
| Review-disposition writes (accept/reject/defer/dispose) | Forbidden — review_policy pinned `preserve_review_state` |
| Mutating any upstream record (workflow/feedback/review/source/draft/packet/projection/context-pack/decision/preference/open-loop) | Forbidden — all read-only inputs |
| Live LLM / Qwen / Ollama | Forbidden — deterministic mapping only |
| `source_file_read` / `SourceContentProvider` / scan / reindex / source-card generation | Forbidden |
| Raw prompt/response, raw email body, full upstream payload copy | Forbidden — bounded ids/metadata only |
| New sanctioned remote write beyond `ai_outputs_card_upsert` | Forbidden — MCP stage tools are read-only |
| N8C-13 operator UI | Deferred — no branch |

## Fixed stage policy (schema CHECK + models + tests)
Stage: `action_policy=no_execution`, `execution_policy=staged_only`, `workflow_policy=staging_only`,
`review_policy=preserve_review_state`, `citation_policy=preserve_citations`,
`source_policy=use_existing_artifacts_only`, `requires_operator_review=1`.
Item: `execution_status=not_executed`, `external_system=none`, `external_ref=NULL`,
`requires_operator_review=1`, `staged_state ∈ {candidate, blocked}`.
