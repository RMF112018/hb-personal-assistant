# 12 — Risk + Defer List

## Deferred (unchanged)
- **N8C-19 Action Staging, Not Action Execution** — durable, source-backed, operator-review-required staging
  of proposed follow-up CANDIDATES (V110 `assistant_action_stage*`). N8C-18 deliberately creates NO
  action-stage table. N8C-19 reads N8C-17 workflow context + N8C-18 feedback recommendations (read-only) and
  branches off the N8C-18 commit.
- **N8C-13 operator UI** — no branch, no UI.
- **N8D `agent_bridge`** — untouched, not imported.

## Residual risks (bounded)
| risk | mitigation |
| --- | --- |
| Feedback misread as a review disposition | schema CHECK pins `review_policy=advisory_review_loop` + `requires_operator_review=1`; no accept/reject/defer/dispose column, command, or tool exists |
| Duplicate feedback rows | deterministic `feedback_id` → idempotent reuse (tested) |
| Provenance/body leakage | bounded caps + whitelisted anchors + redaction assertions across API/CLI/MCP |
| Schema-head test brittleness at future bumps | four head tests made head-agnostic this phase |
| Cross-domain migrator regression | schedule + forecasting bundles run (migrator canary) |

## Stop-and-report triggers honored
No action execution, external integration, N8D, agent_bridge, live LLM, source scan/reindex,
`source_file_read`, vault/raw-source mutation, review-disposition write, MCP write/build tool, N8C-13 UI, or
schema beyond the additive feedback tables (V109) was introduced. The finality guard was not weakened.
