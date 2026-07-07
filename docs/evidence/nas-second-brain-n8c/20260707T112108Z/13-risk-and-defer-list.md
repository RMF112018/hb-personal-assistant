# 13 — Risk & Defer List

## Deferred (intentionally out of N8C-14 scope)
- **N8C-13 operator UI / command center** — deferred. No branch, no UI code, no schema version claimed.
- **Live LLM-client validation** — N8C-14 is a DETERMINISTIC builder (no Ollama/Qwen); live client runs are a
  later NAS validation stage.
- **A frontend surface over the 6 GET routes** — separate UI phase (N8C-13).

## Residual risks (low)
- The 6 remote MCP draft tools are internet-exposed (Cloudflare). Mitigated: read-only DB snapshot
  (`mode=ro&immutable=1` + `PRAGMA query_only=ON`), no write/build/answer/action tool, independent default-ON
  kill switch (`HB_MCP_ASSISTANT_ANSWER_DRAFTS`), bounded limits, and tool names carry no answer-generation
  verb (the substring `answer` is absent from every remote tool name).
- `api.py` carries pre-existing legacy ruff debt (48 errors) outside the new block; left untouched (surgical).
- The `-q` schedule-canary summary line is not always machine-capturable; greenness rests on exit 0 + the
  captured `345 passed`.

## Follow-ups (not blocking)
- N8C-13 UI over these read models (no new writes).
