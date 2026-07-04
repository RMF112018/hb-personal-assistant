# 00 — N3 Closeout (Bounded Copied-DB Creation + NAS Placement Smoke)

**Result: PASS** · Timestamp `20260704T060648Z` · Worktree `ops/nas-copied-db-n3-20260704T060648Z` (base `9e533f6a`)

## What N3 did

Created a safe, read-only-sourced SQLite **backup-API** snapshot of the live ~3.9 GiB Mac DB, placed it on the
Synology NAS at the intended app-support DB path, and validated it end-to-end — including as the demoted
runtime user `personal-assistant-svc`. Not a production cutover; no backend/secrets/vault/scheduler actions.

## Headline proof

| Item | Value |
|---|---|
| Source | live Mac DB, `mode=ro` + `query_only=ON`, **unmodified** (size/mtime/inode identical pre/post) |
| Copy method | `sqlite3` backup API `src.backup(dst)` (reused `launcher/profiles.py` pattern) |
| NAS final path | `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| Ownership / mode | `personal-assistant-svc:users` / `600` (`-rw-------`) |
| Integrity | local `integrity_check=ok`; NAS (bfetting) `ok`; NAS (svc) `integrity=ok`, `quick_check=ok` |
| Hash equivalence | local copy == NAS copy (`4b2d8aab…eccc3`) |
| Schema | `current_version()=98` (source + local); NAS `MAX(schema_migrations.version)=98` |
| Tables | 506 (source, local, NAS) |
| svc identity | `uid=1028(personal-assistant-svc)`, `administrators` absent (demoted, least-privilege) |

## Boundaries held
Live DB never mutated · no migrations run · no secrets/keys/vault/MSAL/Procore copied ·
no backend/container/Portainer/scheduler/watcher/ingestion started · ports 8000/9000/9443 not listening ·
router/firewall/Tailscale untouched · **no N4** · no push.

## Evidence files
`01`–`10` (this dir) + gitignored `local-sensitive/` (SHA files only). Raw `.sqlite` copy lives **outside the
repo** in the session scratchpad. Full details: `09-n3-verdict-and-next-phase.md`.

## Next
N4 (backend-against-copied-DB, further placement, cutover) remains **NOT authorized** until explicitly
authorized in a separate operator instruction.
