# Phase 10 Final Validation Runbook

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


## Closeout

Write `docs/evidence/construction-intelligence-phase-10-local-action-intelligence/13-final-closeout.md` with:

- branch;
- HEAD;
- commits;
- validation command results;
- evidence files;
- known limitations;
- next recommended phase.
