# P09 — Copy Regression Harness, Documentation, and Closeout Evidence

## Objective

Add automated frontend display-copy regression coverage, document the implemented shell/layout/copy rules, and produce closeout evidence.

## Scope

Likely files:

- `frontend/package.json`
- a new frontend or repo-level copycheck script
- tests or proof scripts as appropriate
- `docs/evidence/frontend-ui-ux-shell-layout-implementation/` evidence docs
- route/layout/copy documentation

## Required implementation

1. Add `npm run copycheck` or an equivalent documented command.
2. Scan production-rendered frontend source files:
   - `frontend/src/**/*.tsx`
   - `frontend/src/**/*.ts`
   - `frontend/src/**/*.css`
3. Fail on forbidden production terms unless allowlisted.
4. Allowlist docs/tests/dev-only panels explicitly.
5. Document the shell layout contract, dashboard grid rules, copy standard, and Data Quality footer behavior.
6. Capture closeout evidence and validation results.

## Seed forbidden terms

Use `data/forbidden_terms_seed.json` as the starting list.

At minimum fail on visible production usage of:

- `local dev role`
- `not production auth`
- `Prompt 14B`
- `Prompt 20`
- `FPR-004`
- `raw panels`
- `JSON.stringify`
- `FastAPI`
- `uvicorn`
- `read model`
- `source/sync/evidence`
- `Chat (disabled)`
- `Vite`
- `HMR`
- `Count is`

## Acceptance criteria

- `npm run copycheck` passes.
- `npm run lint`, `typecheck`, `build`, and tests pass or any pre-existing limitation is documented.
- Documentation captures implemented shell/grid/copy rules.
- Closeout report includes changed files, validation, manual smoke, screenshots/evidence, and safety confirmation.
- No P0/P1 gap remains open without explicit operator acceptance.

## Final validation

```bash
cd /Users/bobbyfetting/hb-personal-assistant/frontend
npm run copycheck
npm run lint
npm run typecheck
npm run build
npm run test

cd ..
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py
```

## Closeout

Use `09_CLOSEOUT_REPORT_TEMPLATE.md` from this package.
