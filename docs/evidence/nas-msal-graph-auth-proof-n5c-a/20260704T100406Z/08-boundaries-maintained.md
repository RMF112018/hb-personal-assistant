# 08 — Boundaries Maintained

| Boundary | Status |
|---|---|
| No backend / uvicorn started | ✅ held (default CMD overridden; `running_hbpa=0`) |
| No MCP started | ✅ held |
| No scheduler / watcher started | ✅ held |
| No source ingestion / card generation | ✅ held |
| No production DB writable open / migrate | ✅ held (`db_pre == db_post`) |
| No production config activation beyond read-only config mount | ✅ held (config mounted `:ro`; not placed/activated) |
| No source-root activation / vault migration | ✅ held |
| No Procore proof | ✅ held (out of scope) |
| No Graph data endpoint fetched | ✅ held (Graph smoke deferred) |
| No secrets / tokens / device code / login URL / cache contents in committable evidence | ✅ held |
| No `SQLiteMigrator.apply()` | ✅ held |
| Mac MSAL cache copied | ✅ **not** copied — fresh device-code re-auth used |
| No broad passwordless sudo / no svc direct SSH restored | ✅ held |
| No push / PR | ✅ held |

## What WAS done (bounded, authorized)
- Reconfirmed auth DB-safety (repo truth).
- Auth-path preflight (auth dir 700, no pre-existing cache, DB baseline).
- Bounded network diagnostics (no app-support mount, no login) to isolate a Docker bridge-DNS issue.
- One successful device-code login via `--network host` (after the default-bridge DNS failure), persisting the
  delegated MSAL cache to the NAS as `personal-assistant-svc:users` `600`.
- Post-login metadata + DB side-effect + container-cleanup proofs.
- Redacted evidence (this bundle), left uncommitted.

## Redaction
Account identifier and raw command/login detail are kept in `local-sensitive/` (gitignored). No device code, login URL,
tokens, or MSAL cache contents appear in committable evidence.
