# N8C-21 — API / CLI surface proof

## API (GET-only, per group)
Every N8C read surface under `/api/assistant/*` is GET-only, wrapped in `_assistant_env`
(`guardrails.read_only=true`), all-roles. The newest — `/api/assistant/quality*` (6 routes),
`/api/assistant/action-stages*`, `/api/assistant/feedback*` — are proven GET-only with 404-on-missing and
no write/build route by `tests/test_fastapi_analytics_quality.py`,
`tests/test_fastapi_analytics_action_stages.py`, `tests/test_fastapi_analytics_feedback.py` (all green).

## CLI (dry-run/apply write gate, no execution verbs)
Each writer CLI (`hb-assistant feedback|action-stage|quality`) exposes preview/build(--dry-run/--apply)/list/
show/(summary)/export ONLY — no execute/repair/send/schedule/accept/reject/defer/dispose command. The
`--apply` writer is CLI-only and never exposed remotely. Proven by `tests/test_quality_cli.py`,
`tests/test_action_stage_cli.py`, `tests/test_feedback_cli.py`.
