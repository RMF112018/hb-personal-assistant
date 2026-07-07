# 02 — Current-State Audit (repo truth)

Verified read-only against the worktree before implementing:
- N8C-11 packet contract consumed: `assistant_research_packets.answer_contract_json` +
  `answer_contract_digest`; items carry `answer_role` / `inclusion_state` / `effective_state` / provenance /
  digests; citations carry `citation_id` (→ our `packet_citation_id`) + `citation_type` + anchors.
- Migrator head was `LATEST_SCHEMA_VERSION = 107`; `_v107_statements()` + guarded V107 block at the tail of
  `apply()`. head-consistency canary auto-tracks the head via `LATEST_SCHEMA_VERSION`.
- N8C-12 `SourceIndexRepository.get_source_detail(source_id, conn=)` returns `source_root_key` + (relative)
  `rel_path`; `encode_source_ref` is a pure path-free codec. Neither reads a file.
- The N8C-12 remote MCP test (`test_nas_mcp_source_connector.py`) enforces a finality guard: **no registered
  assistant tool name may contain** `answer` / `generate` / `build` / `send` / `write` / … (substring). This
  drove naming the 6 remote draft tools with `draft` (not `answer_draft`).
