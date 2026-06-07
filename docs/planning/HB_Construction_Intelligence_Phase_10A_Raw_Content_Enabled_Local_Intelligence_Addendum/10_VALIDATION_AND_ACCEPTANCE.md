# 10 Validation and Acceptance

## Evidence directory

`docs/evidence/construction-intelligence-phase-10a-raw-content-enabled-local-intelligence/`

## Validation commands

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

## Runtime validation

```bash
export HB_PA_CONFIG=/tmp/hb-pa-dev-live.yml

hb-assistant diagnostics env --json
hb-assistant graph mail status --json
hb-assistant graph mail discover --lookback-days 30 --max-messages 200 --no-dry-run --json
hb-assistant graph mail thread-summary --lookback-days 30 --max-threads 200 --no-dry-run --json

hb-assistant construction-agent refresh-sources --graph-only --apply --confirm --skip-vector --skip-daily-brief-proof --json
```

## New raw-content proof commands to implement

```bash
hb-assistant graph raw-content status --json
hb-assistant graph mail raw export --lookback-days 30 --max-messages 50 --json
hb-assistant graph calendar raw export --lookback-days 7 --lookahead-days 14 --max-events 50 --json
hb-assistant second-brain action-intel raw-context build --source email --max-threads 20 --json
hb-assistant second-brain action-intel raw-context build --source calendar --max-events 20 --json
hb-assistant second-brain action-intel extract --source email --raw-content --dry-run --json
```

## Acceptance

- Raw email content persists locally when enabled.
- Raw calendar content persists locally when enabled.
- Local API can return raw content.
- Local model receives raw content.
- Model output candidates are materially better than metadata-only baseline.
- Candidate outputs include source references.
- UI can review raw source context.
- No external writeback is introduced.
