# 06 — Validation Results (N1B)

All validation is **local and static** — no Docker build, no container run, no NAS command, no DB/secret/vault access.

## 1) pytest — `tests/test_nas_runtime_scaffold.py`
- Command: `.venv/bin/python -m pytest tests/test_nas_runtime_scaffold.py -q`
- Result: **18 passed** (exit 0).
- Covers invariants 1–17 in `05` (file existence, port 8000, worker kill switch, HB_PA_CONFIG, loopback publish, no /Volumes, no Mac app-support, no live vault, restart not always, read-only config, no scheduler/watcher service, factory+0.0.0.0 CMD, analytics-ui extra, python>=3.12, non-root, NAS-local config, scratch smoke root, .dockerignore exclusions, no secret values).

## 2) check-runtime-safety.sh
- Command: `sh deploy/nas/scripts/check-runtime-safety.sh`
- Result: **RESULT: PASS (all safety invariants hold)** — every line PASS; rendered-config check SKIP (no arg).

## 3) YAML parse of example configs
- `.venv/bin/python -c "yaml.safe_load(...)"` on both example configs → **ok** for
  `hb-pa-config.nas.example.yml` and `hb-pa-config.smoke.example.yml`.

## 4) docker compose config (syntax only — no build, no up)
- Command: `docker compose -f deploy/nas/compose.yaml config` → **VALID**.
- Rendered confirms the safety-relevant fields:
  - `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS: "1"`, `HB_PA_CONFIG: /config/hb-pa-config.yml`
  - port `target: 8000`, `published: "8000"` (host address resolves to the loopback default)
  - `restart: "no"`
  - config mount `source: /volume1/personal-assistant/config/hb-pa-config.yml` → `target: /config/hb-pa-config.yml` (read-only)
  - app-support mount `source == target == /volume1/personal-assistant/app-support`

## 5) smoke-local.sh
- Command: `sh deploy/nas/scripts/smoke-local.sh` → safety **PASS**; YAML step **SKIP** on the Mac's system python (no PyYAML — a venv/container dependency); compose syntax **ok**. (YAML confirmed valid separately via the venv python in step 3 above.)

## Not run (by design)
- **`docker build`** — skipped: it pulls the `python:3.12-slim` base + installs many deps (network-heavy, slow, and unnecessary for scaffold authoring). To be exercised in N1C under operator authorization.
- **`docker compose up`** — not run (would start the backend). Prohibited in N1B.
- No NAS SSH commands were needed for scaffold authoring; none were run this phase.
