# 09 — No Live Source Read / No Raw-Body Persistence

## No source-file read
The feedback layer never opens a source file, never instantiates a `SourceContentProvider`, never calls
`source_file_read`, and never scans/reindexes. Confirmed by the code-symbol guard in
`test_feedback_service.py::test_no_execution_or_external_or_llm_symbols_in_source`.

## Bounded metadata only — no raw bodies
Feedback targets store bounded ids + optional whitelisted anchor ids + an optional bounded `target_digest`
and bounded `metadata_json`. There is no column for, and no code path that copies:
- a raw source/card/vault body,
- a raw email body,
- a full packet/draft/context-pack/projection payload,
- a raw prompt or model response.

## Export is redaction-safe
`export_feedback` returns `feedback_export_v1` = record + targets + recommendations (bounded rows only). The
API, CLI, and MCP tests assert the serialized payload contains none of:
`claim_text`, `evidence_excerpt`, `email_body`, `raw_response`, `prompt`, access/refresh tokens, Bearer/JWT
material, private-key markers, or absolute `/Users/` paths.
