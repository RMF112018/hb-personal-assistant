# 13 — Risk & Defer List

## Deferred (intentionally out of N8C-11 scope)
- **Answer generation** — N8C-11 emits answer-CONTEXT only. Turning a packet into prose is downstream
  (ChatGPT / frontend / future N8D), never here.
- **N8D bridge / orchestration** — no `agent_bridge`, no action execution, no scheduler/worker. When N8D
  merges, schema head resolution must be re-checked (N8C-11 assumed 107 because `agent_bridge` is absent).
- **Non-projection packet sources** — builder is projection-scoped. Packets built directly from
  review/source without a projection are not implemented.
- **Markdown/HTML/PDF export** — export is bounded JSON only.
- **Vector store / graph schema / LlamaIndex** — none added.

## Residual risks (low)
- api.py carries pre-existing legacy ruff debt (B904/I001/B008/F821) outside the N8C-11 block; left
  untouched to keep the change surgical.
- The `-q` schedule-canary summary line is not machine-capturable (documented gotcha); greenness rests on
  exit 0 + all-dots output.

## Follow-ups (not blocking)
- When N8D lands, add a read-only consumer path over research packets (no new writes).
- Consider a frontend surface over the 6 read routes (separate UI phase).
