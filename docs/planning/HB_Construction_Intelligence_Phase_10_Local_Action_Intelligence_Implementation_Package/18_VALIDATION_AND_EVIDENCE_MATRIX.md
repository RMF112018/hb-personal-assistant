# 18 Validation and Evidence Matrix

## Exact validation commands

Run the relevant subset after this prompt and include command output in evidence:

```bash
python -m compileall src tests
ruff check src tests
mypy src
pytest -m "not live and not integration and not manual"

cd frontend
npm install
npm run lint
npm run build
npm test -- --run
```

Phase 10 command checks, once implemented:

```bash
hb-assistant second-brain local-model status --json
hb-assistant second-brain ai-jobs status --json
hb-assistant second-brain ai-jobs run --dry-run --max-items 10 --json
hb-assistant second-brain action-intel extract-fixture --fixture tests/fixtures/local_ai/email_task_candidate_001.json --json
hb-assistant vault status --json
hb-assistant vault index --dry-run --json
hb-assistant second-brain mcp packet build --packet-type daily_brief --date 2026-06-07 --json
hb-assistant construction-agent data-quality no-writeback-proof --json
hb-assistant second-brain mcp data-quality no-raw-access-proof --json
hb-assistant second-brain mcp data-quality no-writeback-proof --json
```


## Evidence folder

`docs/evidence/construction-intelligence-phase-10-local-action-intelligence/`

## Required evidence files

- `00-repo-baseline.json`
- `01-local-model-status.json`
- `02-local-model-fixture-extraction.json`
- `03-ai-job-dry-run.json`
- `04-task-commitment-fixture-proof.json`
- `05-follow-up-monitor-fixture-proof.json`
- `06-relationship-candidate-fixture-proof.json`
- `07-daily-brief-candidate-proof.json`
- `08-obsidian-vault-dry-run-proof.json`
- `09-mcp-packet-proof.json`
- `10-frontend-build-proof.txt`
- `11-no-raw-no-writeback-proof.json`
- `12-final-closeout.md`

## Evidence quality

Every evidence file must include command, generated timestamp, repo SHA, schema version, environment, status, warnings, blockers, counts, and guardrail summary.
