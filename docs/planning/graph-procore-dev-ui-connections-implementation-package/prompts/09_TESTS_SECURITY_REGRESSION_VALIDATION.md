# P08 — Tests, Security Regression Coverage, and Manual Validation

# Validation and Evidence Plan

## Backend validation

```bash
python -m compileall src tests
ruff check src tests
mypy src
pytest -m "not live and not integration and not manual"
```

Targeted tests:

```bash
pytest tests/test_fastapi_analytics_sources_status.py -q
pytest tests/test_fastapi_analytics_graph_status.py -q
pytest tests/test_fastapi_analytics_procore_status.py -q
pytest tests/test_fastapi_analytics_source_refresh_actions.py -q
```

## Frontend validation

```bash
cd frontend
npm install
npm run lint
npm run build
npm test -- --run
```

Also run `npm run typecheck` and `npm run copycheck` if scripts exist.

## Manual Dev validation

```bash
hb-assistant launcher close --environment dev --action quit --json || true
hb-assistant launcher dev --open --open-timeout-seconds 45 --json
hb-assistant launcher status --environment dev --json
```

Browser checklist:

1. Open `http://127.0.0.1:5173`.
2. Navigate to Settings / Connections.
3. Confirm Graph card loads.
4. Confirm Procore card loads.
5. Confirm no console errors.
6. Confirm backend logs show status-only calls on page load.
7. Confirm no live Graph/Procore calls occur from status page.
8. Run local/mock refresh.
9. Run dry-run.
10. Confirm live refresh is disabled or fails closed without config/confirmation.

## Evidence to capture

- branch/HEAD before and after;
- launcher plan/open/status JSON;
- browser screenshot of connection cards;
- browser console/network evidence;
- backend log excerpt;
- validation command outputs;
- changed-file list;
- safety confirmation.


## Additional proof

Add assertions that no writeback routes are exposed and no browser response contains token/secret/cache/raw payload fields.
