# 09 — Next Phase: N1C — Bounded Scratch Container Smoke Test (plan; do NOT run without authorization)

**Scope:** prove the container starts, serves `/health`, and stops cleanly — against a **disposable scratch**
app-support root only. Still **no live DB, no secrets, no vault, no scheduler/watcher**.

## Preconditions (operator confirms)
- Port 8000 free; Portainer still off 8000.
- Memory headroom acceptable at run time (check `free -h`; scratch smoke ≈300–400 MB).
- Decide publish address: loopback (then use an SSH tunnel from the Mac) **or** tailnet `<nas-tailnet-ip>` (only if exposure confirmed). Never `0.0.0.0`.

## Steps
1. Clone/checkout this branch on the NAS (or copy `deploy/nas/`).
2. `render-config.sh smoke` → `/volume1/personal-assistant/config/hb-pa-config.smoke.yml`; run `check-runtime-safety.sh` on it.
3. Export scratch overrides: `HB_APP_SUPPORT_DIR=/volume1/personal-assistant/app-support-smoke`, `HB_CONFIG_FILE=…/hb-pa-config.smoke.yml`; create the scratch dir.
4. `docker compose -f deploy/nas/compose.yaml up -d --build` (first build pulls base + installs deps).
5. Prove:
   - container `Up`/healthy; `HB_SMOKE_OK=1 health.sh` returns a `/health` payload (JSON) from the scratch DB;
   - the app wrote **only** under `…/app-support-smoke` (e.g., `db/hb-personal-assistant.sqlite` created there); **live app-support untouched** (compare mtimes/inventory before/after);
   - no other container affected (`docker ps` diff); Portainer still stopped; workers off (health shows `background_workers_disabled_by_env`).
6. `stop.sh --down`; optionally remove image + scratch root (rollback in `07`).

## Evidence for N1C
- start/health/log/stop transcripts; before/after inventory of live app-support proving no writes; `docker ps` diff; memory before/during/after.

## Explicitly still prohibited in N1C
- No live DB copy, no migration against a live DB, no secrets, no vault, no production restart policy, no `0.0.0.0`, no firewall changes.

## After N1C (future phases, separately authorized)
- **N1D** permissions/user hardening + exposure confirmation (the N1A deferred blockers).
- **N2** safe DB migration (SQLite backup API) + Text-Vault/MSAL/Procore provisioning, then a controlled cutover.
