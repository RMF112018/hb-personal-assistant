# MASTER IMPLEMENTATION PROMPT — Graph and Procore Dev UI Connection Workflows

You are working in `/Users/bobbyfetting/hb-personal-assistant`.

Implement `docs/evidence/graph-procore-dev-ui-connections-implementation-package/`.

Primary objective: make Microsoft Graph/Microsoft 365 and Procore connection/auth/status/refresh workflows usable, clear, and safe from the Dev frontend/UI.

Run P00 through P09 in order. Preserve all no-writeback, no-raw-payload, metadata-only status, Dev-live-OFF, and Production-gated-live constraints.

Required final validation:

```bash
python -m compileall src tests
ruff check src tests
mypy src
pytest -m "not live and not integration and not manual"
cd frontend && npm install && npm run lint && npm run build && npm test -- --run
hb-assistant launcher close --environment dev --action quit --json || true
hb-assistant launcher dev --open --open-timeout-seconds 45 --json
hb-assistant launcher status --environment dev --json
```

Use `09_CLOSEOUT_REPORT_TEMPLATE.md` for final reporting.
