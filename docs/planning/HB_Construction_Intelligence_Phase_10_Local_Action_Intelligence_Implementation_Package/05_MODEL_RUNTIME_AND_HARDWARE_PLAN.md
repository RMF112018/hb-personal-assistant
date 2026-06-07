# 05 Model Runtime and Hardware Plan

## Hardware target

MacBook Pro M4, 24 GB unified memory.

## Model roles

| Role | Default | Notes |
|---|---|---|
| `fast_extract` | `qwen3:8b` | Optional retry/bulk triage profile. |
| `default_extract` | `qwen3:14b` | Phase 10 default. |
| `quality_reasoning` | `gpt-oss:20b` | Daily Brief, MCP packet, nuanced prioritization. |
| `heavy_context` | `qwen3:30b` | Explicitly enabled, manual/on-demand only. |

## Runtime

Use Ollama first.

Reasons:

- local daemon is easy to probe;
- structured outputs can be requested with JSON schema;
- Pydantic validation can be reused;
- local model calls can be isolated from Graph/Procore credentials.

## Required provider abstraction

Do not hardcode Ollama throughout business logic. Add:

- `LocalModelProvider`
- `OllamaLocalModelProvider`
- future placeholders for `MLXLocalModelProvider`, `LlamaCppLocalModelProvider`, and `MockLocalModelProvider`

## Readiness status output

```json
{
  "command": "second-brain local-model status",
  "provider": "ollama",
  "ready": true,
  "profiles": [
    {
      "profile_id": "default_extract",
      "model": "qwen3:14b",
      "available": true,
      "role": "task_commitment_extraction",
      "max_context_tokens": 32768,
      "default_timeout_seconds": 120
    }
  ],
  "blockers": [],
  "guardrails": {
    "external_writeback": false,
    "raw_prompt_persisted": false,
    "raw_response_persisted": false
  }
}
```

## Heavy model restrictions

`qwen3:30b` or equivalent must require:

- explicit config enablement;
- single concurrency;
- max input window cap;
- timeout;
- fallback to `default_extract`;
- thermal/battery warning;
- dry-run proof before scheduled use.
