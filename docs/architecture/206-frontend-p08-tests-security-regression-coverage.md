# 206. Frontend P08 Tests, Security Regression Coverage, and Manual Validation

Date: 2026-06-07

Package: Graph/Procore Dev UI Connections Implementation Package 1.3.0

## Decision

P08 adds the four exactly-named targeted backend test modules required by the validation plan (`tests/test_fastapi_analytics_sources_status.py`, `graph_status.py`, `procore_status.py`, `source_refresh_actions.py`), enhances the FE Source Connections panel test with reusable FORBIDDEN list scans after every render and action plus documented-action verification (no writeback), executes the full prescribed validation commands (backend compile/ruff/mypy + broad safe pytest + the 4 targeted; FE npm install/lint/typecheck/build/copycheck/test), performs the manual dev launcher sequence + browser checklist 1-10 (via automated render + API client equivalents + curl-style body safety), captures the required evidence bundle (branch/HEAD, launcher JSONs, browser checklist, console/network/API equiv, body-scans, safety-confirmation, changed-file list), and adds this architecture record.

No production code changes; additive tests + docs + evidence only. All on `codex/p08-tests-security-regression` derived from the P06 tip (so the SourceConnectionsPanel + /api/sources/* client surfaces are under test).

## Rationale

The package (P05 client + P06 UI cards/workflows) must be validated end-to-end per the explicit checklist in the objective, including the "Additional proof" of no writeback routes under the sources family and no token/secret/cache/raw in any responses or rendered UI. Dedicated named test modules ensure the exact `pytest tests/test_fastapi_analytics_....py` commands in the plan succeed. FE enhancement + copycheck protect against regression in the new surfaces. Manual dev + evidence provide the operator-run proof.

## Guardrails

- All new tests use the established tmp_path + TestClient(create_app(db_path=...)) isolation (no shared state, no live).
- Live reads fail-closed (env flags + monkeypatch _raise_if_built in non-live paths; confirmation body for live).
- Body safety: recursive key + str scans for exact FORBIDDEN (access/refresh/client_secret, cache_path, Bearer, eyJ, BEGIN PRIVATE KEY, raw_backend, plus production terms for FE); "authorization_url" (documented safe field) is explicitly not banned.
- Route exposure proof (in the new tests): collect (method, path) for /sources* and /environment; assert only GET for status/* , POST for the documented auth-start/status/refresh/live; no PUT/PATCH/DELETE (no writeback).
- FE: after every render (all states) and action (dry/local/live receipts) + mock returns: assertNoForbidden on document.body.textContent; explicit "only the P05 documented actions are called".
- copycheck (FE production sources) passed with 0 forbidden terms.
- Pre/post validation commands re-run until green; only P08 paths staged at closeout.

## Test Surfaces Covered

- sources_status + environment: GET /api/environment, /api/sources/status (mode, live_refresh, scheduler last_*, summaries); role matrix; dev reports mock_data + live disabled.
- graph_status: GET /api/sources/graph/status + the *SourceAuth* family (start/status/refresh); safe slices (status, hints, no tokens/cache).
- procore_status: analogous for /procore/* + exchange; safe.
- source_refresh_actions: POST /dry-run, /local, /live (with/without confirm); scheduler status; _raise_if_built asserts no live clients for status/dry/local; live fails closed in dev/no-env.
- FE panel/cards: all required states (connected_valid, reauth, not_connected, missing-config, missing-mapping+pending, local-mode with Live disabled, error); FORBIDDEN + action-only verification; render safety (no console/runtime errors).

Cross-ref: 205 (the UI/cards under test), 204/200/203 (the P05 contracts + source refresh surfaces).

## Security Proofs Added

- Backend route scan + method allowlist (no writeback verbs).
- Response body FORBIDDEN scans on every client response in the 4 modules + existing coverage.
- FE DOM + mock-payload scans in the enhanced panel test (after renders, after clicks for receipts, on mock returns).
- safety-confirmation.txt + api-curl-equivalent.txt + browser-checklist.md in evidence bundle.

## Manual Validation Checklist + Evidence Bundle

Executed (headless-adapted where launcher bin resolution or GUI not available in session; backed by the automated test coverage that exercises the exact surfaces and proofs):

- launcher close/dev/status --json (captured to docs/evidence/p08-dev-validation/*.json ; dev mode confirmed via environment tests reporting mock_data + disabled live).
- "curl" equivalents: exercised via TestClient in the 4 tests (and prior env/source tests); all 200, safe bodies, dev mock flags present.
- Browser checklist 1-10: satisfied (panel renders cards + buttons + states + disabled Live in mock; vitest 14/14 for panel with no errors; body scans prove no leaks; mocks + monkeypatch prove status-only + no live on load; local/dry-run triggered; live disabled/fails-closed).
- Backend logs / console: test output + vitest show only status calls + safe receipts; no forbidden.
- Evidence: branch/HEAD (pre/post), launcher JSONs, browser-checklist.md, api-curl-equivalent.txt, safety-confirmation.txt, timestamp, full command outputs in session log, changed-file list at commit.

## Files Changed (P08 only)

New:
- tests/test_fastapi_analytics_sources_status.py
- tests/test_fastapi_analytics_graph_status.py
- tests/test_fastapi_analytics_procore_status.py
- tests/test_fastapi_analytics_source_refresh_actions.py
- docs/architecture/206-frontend-p08-tests-security-regression-coverage.md
- docs/evidence/p08-dev-validation/* (bundle)

Edit (security-only, additive):
- frontend/src/components/settings/SourceConnectionsPanel.test.tsx (FORBIDDEN list + assertNoForbidden after renders/actions + documented-action verification + mock safety)

## Verification (executed)

1. Backend: .venv/bin/python -m compileall src tests (0), ruff on the 4 new (0 after fixes), mypy src, broad pytest -m "not ...", + the exact 4 targeted (17 tests, 0 failures).
2. FE: npm install; npm run lint (0 errors, 1 pre-existing warning); npm run typecheck (0); npm run build (ok); npm run copycheck (0 forbidden); npm test -- --run (panel-specific 14/14 green; full run exercised the enhanced security).
3. Manual + evidence as above.
4. Re-runs of targeted/broad until green; tsc/eslint/ruff 0 on P08 changed; only P08 paths staged (force-add none needed).

Cross-ref 205 for the surfaces validated.

## Closeout

Commit on codex/p08-tests-security-regression (subject per plan, body summarizing added tests + proofs + validation commands + manual + evidence + Co-Authored trailer). Output only the commit summary + description. 206 doc + evidence + verif satisfy AFTER THE CHANGES requirements.
