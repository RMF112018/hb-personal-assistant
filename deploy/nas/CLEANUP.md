# NAS Cleanup Checklist

Operator hygiene after smoke/benchmark phases. **Review before any persistent service install.**

## Runtime staging repos (safe to delete after evidence committed)

| Path | Phase | Action |
|---|---|---|
| `/volume1/personal-assistant/runtime/n4c-backend-smoke-20260704T075948Z/` | N4C | Delete or archive after evidence in git |
| `/volume1/personal-assistant/runtime/n4c-pr-a-backend-smoke-20260704T092127Z/` | N4C-PR-A | Delete or archive after evidence in git |

Exclude `.git` from NAS copies — repos are disposable staging trees.

## N4B scratch DB copies

| Item | Action |
|---|---|
| `/volume1/personal-assistant/app-support/tmp/sqlite-bench-*` | Delete after benchmark evidence captured |
| Mac `local-sensitive/` bench copies | Keep out of NAS; never commit raw DB |

Any **copied production DB in scratch** must either:

- **Delete** after evidence, or
- Lock to `personal-assistant-svc:users` with directories **700** and files **600**.

## Temporary logs

| Path | Action |
|---|---|
| `/volume1/personal-assistant/app-support/logs/n4c-backend-smoke-*.log` | Review; delete if no unique evidence |
| `/volume1/personal-assistant/app-support/logs/n4c-pr-a-backend-smoke-*.log` | Review; delete if redundant with git evidence |

Do not commit logs that may contain paths/secrets to git.

## Smoke scripts on NAS runtime paths

| Item | Action |
|---|---|
| `n4c-smoke-run.sh`, `n4c-pr-a-smoke-run.sh` in runtime dirs | Delete or chmod **700** after use |
| N4C script mode tightened **777 → 700** (operator) | Keep **700** |

Canonical scripts live in repo: `deploy/nas/scripts/`.

## Unused Docker artifacts

```sh
# List HB images
sudo docker images hb-personal-assistant

# Optional prune dangling layers (HB project only — review first)
sudo docker image ls -f dangling=true
```

Do not remove the current `hb-personal-assistant:nas` tag if viewer testing continues.

## Production paths — do NOT delete

- `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`
- `/volume1/personal-assistant/config/hb-pa-config.yml`
- DSM snapshots (useful supplement; not sole DB backup strategy — PR B deferred)

## After cleanup

Run read-only validation:

```sh
deploy/nas/scripts/validate-db.sh
```

Confirm no backend left running:

```sh
deploy/nas/scripts/status.sh
deploy/nas/scripts/emergency-shutdown.sh
```
