# 02 — Runtime Design (repo-truth, N1B)

All citations verified in this worktree at commit `d54f07dd`.

## Entry point & health
- Factory: `create_app(*, db_path: str | None = None)` — `src/hb_assistant/construction/analytics/api.py:781`.
- Health route: `@app.get("/health")` → `def health(...)` — `api.py:824-825`. **Touches the DB** (reads schema version) → must only be exercised against a scratch app-support root in smoke.

## Background workers (must stay disabled)
- Lifespan `_forecast_lifespan` wired at `api.py:798`; defined `api.py:671`. It starts, when NOT disabled:
  - quality-poll loop `_quality_poll_loop` (`api.py:709`), scheduled at `api.py:724` — **writes DB**;
  - source-root registration `register_source_roots(...)` (`api.py:743`) — **writes DB**;
  - `SourceWatcher` (`api.py:737,747`).
- **Kill switch:** `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` — `src/hb_assistant/construction/schedule_clean_db/diagnostics.py:11-12` (`== "1"`). The scaffold sets it in both the Dockerfile ENV and compose `environment`.

## Path resolution (the relocation seam)
- `PathsConfig.application_support_root` default `~/Library/Application Support/HB Personal Assistant` — `src/hb_assistant/config/models.py:34`.
- `PathPolicy.get_app_support()` reads that key — `src/hb_assistant/config/path_policy.py:57,61`; `get_db_path()` = `<app_support>/db/hb-personal-assistant.sqlite` — `path_policy.py:72`.
- **Config loader precedence** — `src/hb_assistant/config/loader.py:34-52`: (1) repo `config/config.yml` if present, then (2) `HB_PA_CONFIG` env file — **shallow-merged** (top-level keys replaced). Implication: providing a `paths:` block in `HB_PA_CONFIG` fully defines paths.
  - The image **excludes** repo `config/config.yml` (via `.dockerignore`), so `HB_PA_CONFIG` is the sole config source in the container (no Mac paths / tenant IDs baked in).

## Launch command (repo-truth)
- Common local command: `python -m uvicorn hb_assistant.construction.analytics.api:create_app --factory --host 127.0.0.1 --port 8000` (launcher `src/hb_assistant/launcher/service.py:123-144`).
- For the container, uvicorn binds `0.0.0.0` **inside the container namespace**; host exposure is controlled by the compose publish (loopback by default). No launcher/scheduler subsystem is started (only the factory).

## Packaging
- `requires-python = ">=3.12"` — `pyproject.toml:10`. Backend web deps are the optional extra `analytics-ui = ["fastapi>=0.115","uvicorn>=0.30"]` — `pyproject.toml:96-98`. Build backend: setuptools.

## Frontend / CORS
- Frontend API base is env-driven (`VITE_API_BASE`); backend has **no CORS** (same-origin design). The scaffold serves the backend only; a same-origin SPA strategy (or explicit CORS) is deferred to a later phase (see `09`).

## Pre-existing deployment scaffold
- **None.** No `Dockerfile`, `compose.y*ml`, `docker-compose*.yml`, or `.dockerignore` existed (`find` returned nothing); no `deploy/` directory. This scaffold is greenfield under `deploy/nas/`.
