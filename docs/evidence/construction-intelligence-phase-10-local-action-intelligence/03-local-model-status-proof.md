# Phase 10 Prompt 03 — Local Model Runtime Status Proof

**Status:** not_ready · **provider:** mock · **generated_utc:** 2026-06-07T21:33:44.396386+00:00

- repo_sha: `f294eeac82d481fcf0a53f4f66dd4a2eff7bf3db`
- endpoint: `mock://local` (mock) · daemon_reachable: False · ready: False
- present_models: []
- required_models: ['qwen3:14b'] · missing_required: ['qwen3:14b']
- blockers: ['daemon_unreachable']

## Profiles

| Profile | Model | Enabled | Heavy | Available | Blocked reason |
| --- | --- | --- | --- | --- | --- |
| fast_extract | qwen3:8b | False | False | False | daemon_unreachable |
| default_extract | qwen3:14b | True | False | False | daemon_unreachable |
| quality_reasoning | gpt-oss:20b | False | False | False | daemon_unreachable |
| heavy_context | qwen3:30b | False | True | False | heavy_profile_requires_explicit_enable |

## Guardrails

Local-first; readiness via `/api/tags` only (no generation); errors redacted to category codes (no raw body/URL/token); heavy profiles blocked unless explicitly enabled; status is read-only (no DB write, no persistence, no external writeback).
