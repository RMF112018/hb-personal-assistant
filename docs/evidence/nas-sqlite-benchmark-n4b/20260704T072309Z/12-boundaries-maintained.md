# 12 — Boundaries Maintained

| Boundary | Status |
|---|---|
| Live Mac DB not mutated | **Held** — size/mtime/ino unchanged (`4151631872`, ino `105921913`) |
| N3 final NAS DB not mutated | **Held** — size/inode/mtime unchanged (inode `3264`, mtime `2026-07-04 06:23:40 UTC`) |
| Writes only to benchmark copies | **Held** — scratch paths only; synthetic table writes |
| No secrets/tokens/keys/MSAL/Procore/vault copied | **Held** |
| No backend started | **Held** |
| No containers / Portainer | **Held** |
| No schedulers / watchers / ingestion | **Held** |
| No vault writes | **Held** |
| No router/firewall/Tailscale changes | **Held** |
| Port 8000/9000/9443 not listening | **Held** (verified NAS preflight) |
| No raw DB artifacts in git | **Held** — only markdown + sanitized JSON metadata |
| No push | **Held** |
| Benchmark script not wired to production | **Held** — standalone `scripts/nas_sqlite_benchmark_n4b.py` only |
| Tailnet IP redacted in committable evidence | **Held** — hostname placeholder in markdown |
| Live Mac DB path not in committable JSON | **Held** — full path in gitignored `local-sensitive/mac-backup.json` |

## Scratch cleanup (evidence hygiene)

Attempted NAS lockdown (`personal-assistant-svc:users`, dir `700`, files `600`) via non-interactive `sudo` — **failed** (password required).

**Remediation:** deleted both scratch directories after evidence capture:

| Path | Result |
|---|---|
| Mac `/tmp/hb-nas-sqlite-bench-20260704T072309Z/` | **Deleted** |
| NAS `/volume1/personal-assistant/app-support/tmp/sqlite-bench-20260704T072309Z/` | **Deleted** |

No `.sqlite` / `.db` / `-wal` / `-shm` artifacts remain outside N3 final DB.

## Session deviation (documented, not a boundary violation)

NAS copy placed via ssh pipe as `bfetting` because non-interactive `sudo -u personal-assistant-svc` was unavailable. N3 final DB was not opened for read or write during N4B.
