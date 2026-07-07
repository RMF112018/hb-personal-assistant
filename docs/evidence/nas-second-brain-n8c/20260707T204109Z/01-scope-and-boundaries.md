# 01 — Scope and Boundaries

## In scope (N8C-18)
- Durable capture of bounded OPERATOR feedback on existing N8C artifacts.
- Preserved provenance: every feedback target carries a mandatory `target_kind` + `target_id` plus optional
  typed upstream anchors (bounded ids only — never a body/payload).
- Deterministic, ADVISORY, operator-review-required review-loop recommendations derived from the feedback
  type.
- Feedback-owned V109 schema (5 tables) + models + repository + service + CLI writer + read-only API + six
  read-only remote MCP tools.

## Explicitly OUT of scope (deferred / forbidden)
| Concern | Status |
| --- | --- |
| Action staging (`assistant_action*` tables/models/builder) | **N8C-19** — not in this phase; no such table exists |
| Review-disposition writes (accept/reject/defer/dispose) | Forbidden — feedback is advisory only |
| Mutating any upstream record (workflow/review/source/draft/packet/projection/context-pack/decision/preference/open-loop) | Forbidden |
| Execution / scheduler / automation / external task | Forbidden |
| Email / calendar / reminder / Slack / N8D `agent_bridge` | Forbidden — untouched, not imported |
| Live LLM / Qwen / Ollama | Forbidden — deterministic derivation only |
| `source_file_read` / `SourceContentProvider` / scan / reindex / source-card generation | Forbidden |
| External sync (Procore / Sage / Graph) | Forbidden |
| Raw prompt/response, raw email body, full upstream payload copy | Forbidden — bounded ids + metadata only |
| New sanctioned remote write beyond `ai_outputs_card_upsert` | Forbidden — MCP feedback tools are read-only |
| N8C-13 operator UI | Deferred — no branch |

## Fixed policy (schema CHECK + models + tests)
`action_policy=no_execution`, `execution_policy=feedback_only`, `review_policy=advisory_review_loop`,
`source_policy=preserve_source_truth`, `citation_policy=preserve_citations`, `requires_operator_review=1`.
If `resolved`/`acknowledged` is used it means the feedback RECORD's own lifecycle — never a review
disposition.
