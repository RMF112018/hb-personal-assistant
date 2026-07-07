# N8C-21 — workflow / feedback / action-stage / quality read smokes

`scripts/n8c-mcp-smoke.sh` (LOCAL, read-only, temp DB) dispatches a representative read per group through the
broker and asserts each returns `ok`. Full transcript in `05b-smoke-output.txt`. Highlights:

```
PASS fresh temp DB migrates to head 111
PASS 78 assistant tools registered (13 groups)
PASS finality guard: no assistant tool has a forbidden verb
PASS ai_outputs_card_upsert is the only non-plan write tool
PASS hb_mcp_status advertises 13 assistant groups
PASS read-only dispatch ok: assistant_list_research_packets
PASS read-only dispatch ok: assistant_list_drafts
PASS read-only dispatch ok: assistant_source_roots_list
PASS read-only dispatch ok: assistant_list_feedback
PASS read-only dispatch ok: assistant_list_action_stages
PASS read-only dispatch ok: assistant_list_quality
PASS denied: raw_sql / sql / shell / exec / read_file_absolute / hb_output_delete
n8c-mcp-smoke: PASS (read-only, temp DB, no writes, no finality-verb tools)
```

Behavioural coverage of the newest groups is additionally proven by `tests/test_nas_mcp_workflows.py`,
`tests/test_nas_mcp_feedback.py`, `tests/test_nas_mcp_action_stages.py`, `tests/test_nas_mcp_quality.py`
(all green) — each seeds real records and asserts the tools return bounded, advisory, non-executing data
over the read-only snapshot.
