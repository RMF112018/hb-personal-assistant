# Evidence — Forecast UI Live App Launch Bootstrap

**Phase:** Forecast CLI→UI product, Live App Bootstrap/Launcher
**ADR:** `docs/architecture/278-forecast-ui-launch-bootstrap.md`
**Runbook:** `docs/runbooks/forecast-ui-launch-bootstrap.md`
**Date stamp:** 20260621T070000Z

## What shipped

When the app launches, the forecast **write-roots** (runs / eval / config-edit) are ensured and a
redaction-safe readiness report is surfaced, so the write-backed forecast surfaces serve real data
out of the box. Read-roots stay strictly fail-closed (never auto-invented).

- `forecast_bootstrap.ensure_forecast_roots()` — the single mutation site; creates only
  configured+valid write-roots, returns the `build_runtime_status()` shape + coded `created` keys.
- `create_app` lifespan hook (`_forecast_lifespan`) — runs the bootstrap on ASGI startup;
  exception-swallowing; no-op when unconfigured (covers manual `uvicorn --factory`).
- `LauncherService._child_env` — auto-defaults the 3 write-roots under `<app-support>/analytics/forecast/`
  for dev+production, only when unset (operator config wins); read-roots never defaulted.
- `LauncherService.start` — non-fatal `forecast_readiness` block (skipped for `--plan`).
- `_write_root_blocker` creatability fix — a write-root with missing-but-creatable parents is now
  correctly creatable (mirrors `mkdir(parents=True)`); required for the nested app-support defaults.

## Proof files

- `test_output.txt` — focused backend suite: **111 passed** (bootstrap, runtime-config, fastapi
  runtime route, app-shell incl. lifespan-noop, launcher).
- `live_launch_smoke_proof.txt` — **real `uvicorn` subprocess** smoke (isolated temp roots):
  `SMOKE_OK` — lifespan created all 3 write-roots, `data_root` left empty (no write under read-root),
  `run_center` ready, zero redaction leaks.
- `cfr_test_posture.txt` — CFR subrepo **565 passed** (unchanged; no CFR change this phase).
- `db_schema_version.txt` — no DB/migrator/schema change; committed `LATEST_SCHEMA_VERSION = 61`.
- `preexisting_failures.txt` — the 2 env-sensitive failures confirmed pre-existing (reproduced on
  clean committed code with this phase's changes stashed out).
- `git_state.txt` — scoped change list (explicit pathspec; no Procore/migrator/unrelated churn).

## Guardrails preserved

- No new HTTP route (readiness rides existing `/api/forecast/runtime/status`); exact-set OpenAPI
  allowlist + `surfaces_ready` exact-dict assertions untouched.
- Structural redaction: readiness payloads carry coded enums + root keys only (live smoke asserts
  `find_redaction_leaks == []` over real paths).
- Read-roots fail-closed; only the launcher auto-defaults write-roots; manual `uvicorn` + tests stay
  fail-closed. No live writes; real live DB/data untouched.

## Pending / deferred

- Frontend unchanged (already GETs the status surface); no build needed.
- Live app run against the real Tropical inputs still requires the operator to configure read-roots
  (package_roots / data_root / db_path) via the Settings page — by design.
