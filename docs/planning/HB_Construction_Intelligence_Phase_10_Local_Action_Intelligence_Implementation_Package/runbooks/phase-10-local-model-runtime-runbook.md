# Phase 10 Local Model Runtime Runbook

## Install/check

```bash
ollama --version
ollama list
ollama pull qwen3:14b
ollama pull gpt-oss:20b   # optional quality profile if available in local registry
ollama pull qwen3:30b     # optional heavy profile, manual use only
hb-assistant second-brain local-model status --json
```

## Recommended first validation

```bash
hb-assistant second-brain action-intel extract-fixture   --fixture tests/fixtures/local_ai/email_task_candidate_001.json   --json
```

## Troubleshooting

- If Ollama daemon is offline, status should return `ready=false`, not crash.
- If a configured model is missing, report the missing profile and fallback.
- If structured JSON validation fails, write a failed receipt with hashes only.
