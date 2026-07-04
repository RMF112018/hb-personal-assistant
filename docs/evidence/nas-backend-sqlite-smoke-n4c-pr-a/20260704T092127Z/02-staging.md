# 02 — Staging (fresh path)

| Item | Value |
|---|---|
| Runtime root | `/volume1/personal-assistant/runtime/n4c-pr-a-backend-smoke-20260704T092127Z` |
| Repo path | `.../repo` |
| Method | `tar` over SSH pipe |
| Staged size | ~308 MB |
| Commit marker | `9bcf7e2ec05e23603e84609be5aae5b580769ece` |

## Exclusions

`.git`, `.venv`, caches, `local-sensitive`, raw `*.sqlite` / WAL / SHM, `node_modules`

## PR A files confirmed on NAS

- `src/hb_assistant/config/db_storage_guard.py`
- `src/hb_assistant/store/startup_schema_policy.py`
- `src/hb_assistant/store/db_posture.py`
- `deploy/nas/compose.yaml` includes `HB_NAS_RUNTIME: "1"`

## Old N4C staged repo

**Not reused.** Fresh path created per authorization.
