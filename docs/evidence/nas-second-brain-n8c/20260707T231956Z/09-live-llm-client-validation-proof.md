# N8C-21 — live LLM-client validation (procedure + bounds)

Performed by the operator from a live MCP client (Claude/Grok remote MCP over the tunnel) AFTER redeploy. Not
performed in this phase (no live LLM is invoked here). Read-only tools only.

Procedure:
1. `hb_mcp_status` → confirm all 13 assistant groups enabled + their tool lists.
2. One representative READ per new group: `assistant_list_action_stages`, `assistant_list_quality`, a workflow
   route → confirm bounded advisory results, non-executing.
3. Confirm no write/build/apply/evaluate/repair tool is offered; confirm `ai_outputs_card_upsert` is the only
   write.

Evidence bounds (clarification #10): capture ONLY tool names, counts, and status booleans. NEVER capture raw
private prompts, raw MCP payloads with private data, full source/file contents, raw email bodies, credentials,
tunnel tokens, or unbounded DB/private paths. Any captured transcript must pass
`scripts/obsidian_evidence_redaction_check.py`.

The LOCAL analogue of this validation (same tools, temp DB, no tunnel) is proven now by `n8c-mcp-smoke.sh`
(`05b-smoke-output.txt`) and the inventory tests — so the surface is known-good before the operator runs the
live pass.
