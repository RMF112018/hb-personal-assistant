# 08 — Known Blockers Before Smoke (N1B → N1C)

The scaffold is authored and statically validated, but these must be respected/resolved before any container start.

## Must be respected during the N1C scratch smoke
- **No live DB copy authorized** — smoke uses a disposable `app-support-smoke` root only.
- **No secrets authorized** — none in config/image; do not add.
- **`/health` may touch/migrate the DB** — only ever against the scratch root (guarded by `HB_SMOKE_OK=1` in `health.sh`).
- **Portainer must remain OFF port 8000** — do not restart it there.
- **Publish loopback only** (or, if reaching from the Mac is needed for the smoke, the tailnet IP `100.66.28.14`) — **never `0.0.0.0`**.
- **Operator must explicitly authorize** any NAS container start (build + up).
- **Background workers/watchers/schedulers stay disabled** (`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`).

## Should be resolved before production (not required for scratch smoke)
- **auth/security ACL hardening unresolved** — 0777 + broad ACL; hard prerequisite before any secret (N1A `04`).
- **Public WAN exposure unconfirmed** — DSM firewall + router + Tailscale Funnel need operator confirmation (N1A `06`).
- **Memory headroom marginal** — ~1.9 GiB available after N1A; a brief scratch smoke (backend ≈300–400 MB) fits, but avoid sustained load; add RAM before real hosting.
- **Runtime-user/admin split unresolved** — `personal-assistant-svc` still in `administrators` (N1A `03`).

## Not addressed in this phase (by scope)
- No live DB migration path executed (documented only; SQLite backup API in future).
- Frontend reachability (same-origin SPA vs CORS) deferred — backend-only scaffold.
