# Validation Commands

## Branch guard

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
```

## CLI discovery

```bash
.venv/bin/hb-assistant second-brain --help
.venv/bin/hb-assistant second-brain local-model --help
.venv/bin/hb-assistant second-brain daily-brief --help
.venv/bin/hb-assistant second-brain pipeline --help
.venv/bin/hb-assistant second-brain daily-run --help || true
```

## Model/router commands

```bash
.venv/bin/hb-assistant second-brain local-model status --json
.venv/bin/hb-assistant second-brain local-model profiles --json
.venv/bin/hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
.venv/bin/hb-assistant second-brain local-model eval --suite daily-brief --models auto --json
```

## Daily brief commands

```bash
.venv/bin/hb-assistant second-brain daily-brief intelligence --date YYYY-MM-DD --dry-run --json
.venv/bin/hb-assistant second-brain daily-run run --dry-run --with-intelligence --json
```

## Test commands

Adjust filenames to implementation truth:

```bash
.venv/bin/python -m pytest tests/test_phase_10_structured_output.py
.venv/bin/python -m pytest tests/test_local_model_eval.py
.venv/bin/python -m pytest tests/test_local_model_router.py
.venv/bin/python -m pytest tests/test_daily_brief_intelligence.py
.venv/bin/python -m pytest tests/test_phase_10_daily_brief_synthesis.py
.venv/bin/python -m pytest tests/test_phase_10_daily_brief_render.py
.venv/bin/python -m pytest tests/test_phase_10_pipeline.py
.venv/bin/python -m pytest tests/test_phase_10_daily_run.py
.venv/bin/python -m pytest tests/test_agent_registry.py tests/test_second_brain_agents_cli.py
```

## Quality commands

```bash
.venv/bin/ruff check src/hb_assistant tests
.venv/bin/ruff format --check src/hb_assistant tests
.venv/bin/mypy src/hb_assistant
```

## Forbidden content scan examples

Adjust to repo scripts if existing:

```bash
grep -RInE 'https?://|join_url|access_token|refresh_token|Bearer|BEGIN PRIVATE KEY|@[^ ]+\.[^ ]+' docs/evidence/phase-10-local-model-routing || true
grep -RInE 'raw_prompt|raw_response|messages_json|body_html|body_text' docs/evidence/phase-10-local-model-routing || true
```
