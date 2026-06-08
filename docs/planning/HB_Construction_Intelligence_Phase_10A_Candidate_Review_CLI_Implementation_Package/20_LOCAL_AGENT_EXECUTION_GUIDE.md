# 20 Local Agent Execution Guide

## Working rule

Repository truth is authoritative. This package is a guide, not a patch.

## Before editing

```bash
git status --short
git rev-parse HEAD
python - <<'PY'
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION
print(LATEST_SCHEMA_VERSION)
PY
```

## Development posture

- Work in small commits or staged checkpoints.
- Keep extraction behavior unchanged.
- Write tests with fixtures rather than live model calls.
- Do not require Ollama for review CLI tests.
- Do not require Graph/Procore/email/calendar credentials for review CLI tests.

## Final response expected from local agent

Include changed files, schema changes, command surface implemented, tests run, validation output summary, evidence path, known limitations, and next command for Bobby to run.
