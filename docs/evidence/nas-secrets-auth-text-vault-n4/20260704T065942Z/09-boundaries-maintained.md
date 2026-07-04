# 09 — Boundaries Maintained

## Attestation — this pass made ZERO changes to the NAS or the DB
| Boundary | Held? | Evidence |
|---|---|---|
| No NAS writes | ✔ | Only read-only `stat`/`ls` over SSH; no file created/moved/chowned; `security/text-vault` still absent |
| No `security/text-vault` created, no key/blob copied | ✔ | Deferred by operator decision; not executed |
| No DB opened in write mode | ✔ | All DB reads via the **local copy** `mode=ro`; NAS DB never opened (write-safety below) |
| Live Mac DB untouched | ✔ | N3 source unmodified; this pass read only the scratchpad copy + source vault metadata |
| No secret values / decrypted content printed or committed | ✔ | Counts/columns/paths-as-placeholders only; existence checks (no blob content, no decrypt) |
| No backend / container / MCP start | ✔ | Nothing launched |
| No scheduler / watcher / ingestion | ✔ | None enabled |
| No vault / source-root migration | ✔ | None |
| No Cloudflare / MCP expansion | ✔ | None |
| No direct svc SSH / broad passwordless sudo | ✔ | All SSH as bfetting; no sudo used at all this pass |
| No push / no PR / not based on origin/main | ✔ | See 11 |

## DB write-safety rationale (why the NAS DB was never opened)
`SQLiteMigrator.apply()` has no version guard — opening the ambient DB (via the app/`ConstructionStore`/lifespan
`ensure_forecast_managed_storage`) runs a WRITE transaction and sets `PRAGMA journal_mode=WAL` even at v98. To keep
the copied DB immutable, all reference/coherence reads used the sha-verified local copy `mode=ro`. Any future NAS
smoke must target the `app-support-smoke` scratch root, never the copied app-support DB.

## sudo posture
No sudo invoked this pass. The deferred Text Vault copy's privileged step (write into `700 svc` `security/`) is
explicitly reserved for operator interactive sudo under a separate authorization.
