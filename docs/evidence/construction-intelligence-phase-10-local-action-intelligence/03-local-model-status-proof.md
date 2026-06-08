# Phase 10 Prompt 03 — Local Model Runtime Status Proof

**Status:** ready · **provider:** mock · **generated_utc:** 2026-06-08T09:28:19.111722+00:00

- repo_sha: `db4d8bc4a2696ba31168bd1510034bf8f03ebea5`
- endpoint: `mock://local` (mock) · daemon_reachable: True · ready: True
- present_models: ['llama3.1:8b', 'mistral-nemo:12b', 'qwen2.5:14b']
- required_models: ['mistral-nemo:12b'] · missing_required: []
- blockers: []

## Profiles

| Profile | Model | Enabled | Heavy | Available | Blocked reason |
| --- | --- | --- | --- | --- | --- |
| default_extract | mistral-nemo:12b | True | False | True | None |
| high_recall_extract | llama3.1:8b | True | False | True | None |
| review_filter | qwen2.5:14b | True | False | True | None |
| quality_reasoning | gpt-oss:20b | False | False | False | profile_disabled |
| heavy_context | qwen3:30b | False | True | False | heavy_profile_requires_explicit_enable |

## Guardrails

Local-first; readiness via `/api/tags` only (no generation); errors redacted to category codes (no raw body/URL/token); heavy profiles blocked unless explicitly enabled; status is read-only (no DB write, no persistence, no external writeback).
