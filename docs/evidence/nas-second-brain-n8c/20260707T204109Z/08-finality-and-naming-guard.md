# 08 — Finality + Naming Guard

## The 23-substring finality guard is preserved and covers the new tools
`_FORBIDDEN` (in `tests/test_nas_mcp_workflows.py`): extract, apply, write, create, delete, persist, upsert,
close, reopen, accept, reject, defer, dispose, build, send, remind, answer, generate, scan, reindex, rebuild.
(Plus the answer-draft superset adds final_answer/answer_text/etc.)

`test_nas_mcp_workflows.py::test_existing_finality_guard_still_passes` registers ALL assistant tools (now
including the six N8C-18 feedback tools) and asserts no registered name contains any `_FORBIDDEN` substring.
It ran green in the regression subset.

## The six feedback tool names are clean by construction
| tool | forbidden substrings? |
| --- | --- |
| `assistant_list_feedback` | none |
| `assistant_get_feedback` | none |
| `assistant_get_feedback_targets` | none |
| `assistant_get_feedback_recommendations` | none |
| `assistant_get_feedback_summary` | none |
| `assistant_get_feedback_export` | none (`export` ≠ `extract`) |

## Guard not weakened
No `_FORBIDDEN` entry was removed or relaxed. No new sanctioned remote write was added.
`ai_outputs_card_upsert` remains the single sanctioned remote write; feedback MCP tools are strictly
read-only over an RO snapshot.
