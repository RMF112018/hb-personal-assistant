# 00 — Closeout

**Phase:** N4C-PR-A bounded NAS backend re-smoke (PR A hardening validation)  
**Result:** **PASS**

## Branch / commit / image

| Item | Value |
|---|---|
| Branch | `feat/nas-sqlite-hardening-pr-a` |
| Commit | `9bcf7e2ec05e23603e84609be5aae5b580769ece` |
| Evidence TS | `20260704T092127Z` |
| Image | `hb-personal-assistant:nas` |
| Image ID | `d18715bf714c` |

## Verdict summary

| Check | Result |
|---|---|
| NAS DB storage guard (intended NAS-local path) | **PASS** — `db_storage_class=nas_local` |
| Startup migration policy (schema == 98, no silent migrate) | **PASS** — `startup_migration_performed=false` |
| Lifespan guard/schema under `HB_NAS_RUNTIME=1` | **PASS** — service started; no guard/policy errors |
| `/health` sanitized posture | **PASS** — no paths/uid/mode on public health |
| `/api/admin/db/status` metadata only (admin) | **PASS** |
| Admin schema counts (PR A semantics) | **PASS** — `table_count=505`, `view_count=2`, `schema_object_count=507` |
| Loopback bind only | **PASS** — `127.0.0.1:8000` |
| Workers / ingestion / schedulers | **PASS** — disabled; logs show safe GETs only |
| Post-smoke DB integrity | **PASS** — `quick_check=ok`, schema **98**, counts unchanged |
| Clean shutdown | **PASS** — compose down; no LISTEN on 8000 |

## Count semantics correction

PR A counts **application** objects only (`type='table'` / `type='view'`, excluding `sqlite_%` internal catalog names).

| Metric | PR A smoke value | Note |
|---|---|---|
| `table_count` | **505** | Application tables |
| `view_count` | **2** | Application views |
| `schema_object_count` | **507** | Sum |

Earlier N3/N4C **506** table reports included `sqlite_sequence` when counting all non-`sqlite_%` tables without the PR A admin helper semantics alignment. This is **not** schema drift.

## Non-blocking follow-ups

| Item | Note |
|---|---|
| `foreign_keys=0` in `/api/admin/db/status` | Admin posture probe uses a read-only URI connection without applying runtime `PRAGMA foreign_keys=ON`; runtime writes via `get_connection()` still set FK enforcement. Track as telemetry follow-up. |
| `db_posture_at_startup` log line | Not visible in captured compose log tail; startup succeeded and admin posture fields match. Consider raising log level or explicit startup banner in a later hardening pass. |

## Operator notes

- Script execution corrected from `sh` to **`bash`** for pipefail/heredoc compatibility.
- Smoke script mode tightened from **777 → 700** on NAS runtime path.
- Build: `docker build --network host` (build-time DNS only).
- Runtime: `docker compose up --no-build -d` (no host networking at runtime).

## Hard boundaries

Maintained: no push, no Cloudflare/Tailscale exposure changes, no secrets/workers/ingestion enablement, no Portainer restart, no passwordless sudo restoration, no N5/cutover.

## Git / push

| Item | Status |
|---|---|
| Local evidence commit | This closeout |
| Push | **Not authorized** |
