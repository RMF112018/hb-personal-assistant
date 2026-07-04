# 07 — NAS Operator Runbook (evidence copy)

Canonical runbook: **`deploy/nas/README.md`** (in this branch). Summary below; start commands are DEFERRED.

## Prerequisites before any start
- Port 8000 free; **Portainer must stay off 8000** (do not restart it there).
- auth/security permissions hardened before any secret.
- Public exposure confirmed safe (DSM firewall + router + Tailscale).
- Memory headroom sufficient; no sustained load without approval.

## NAS paths
- `/volume1/personal-assistant` · config `/volume1/personal-assistant/config/hb-pa-config.yml` ·
  app-support `/volume1/personal-assistant/app-support` · scratch `…/app-support-smoke`.

## Flow
1. **Config:** `deploy/nas/scripts/render-config.sh nas` (or `smoke`) — copies example + validates; add no secrets.
2. **Validate:** `deploy/nas/scripts/check-runtime-safety.sh /volume1/personal-assistant/config/hb-pa-config.yml` and `smoke-local.sh`.
3. **Start — DEFERRED** (do not run without authorization; scratch smoke only):
   `export HB_APP_SUPPORT_DIR=/volume1/personal-assistant/app-support-smoke; export HB_CONFIG_FILE=…/hb-pa-config.smoke.yml; cd deploy/nas && docker compose up -d --build`
4. **Health (scratch only):** `HB_SMOKE_OK=1 deploy/nas/scripts/health.sh`.
5. **Stop:** `deploy/nas/scripts/stop.sh` (or `--down`).
6. **Logs:** `deploy/nas/scripts/logs.sh`.
7. **Rollback:** `stop.sh --down`; optionally `docker image rm hb-personal-assistant:nas` and `rm -rf …/app-support-smoke`. Never touches live app-support/DB/secrets/other containers/packages.

## DO NOT
- No live DB copy · no secrets copy · no `/Volumes` DB path · no live vault/source-roots mount ·
  no Portainer on 8000 · no workers/watchers/schedulers · never point smoke at a live DB.

## Future DB migration (later phase)
- SQLite **backup API** only (`launcher/profiles.py:214-223`), never raw copy of a hot WAL DB; move
  Text-Vault key + `.enc` blobs + DB together; re-provision MSAL/Procore on the NAS.
