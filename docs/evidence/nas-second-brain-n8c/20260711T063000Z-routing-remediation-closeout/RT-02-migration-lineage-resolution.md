# RT-02 — Migration lineage resolution

**Date:** 2026-07-11  
**Disposition:** `CLOSED` — dual-DB design; not a missing migration on deploy.

## Finding (audit)

The July 10, 2026 routing audit reported schema **119** on the RO snapshot while repo head is **121**
(`LATEST_SCHEMA_VERSION`). The audit flagged this as “resolve before next deployment.”

## Repo truth

| Signal | Value | Meaning |
|--------|-------|---------|
| `LATEST_SCHEMA_VERSION` | **121** | Authoritative migrator head (`src/hb_assistant/store/migrator.py`) |
| V120 | `pa_client_tool_manifest` entry classification columns | Manifest entry metadata |
| V121 | `pa_client_tool_manifest` gateway/exposure payload columns | Client manifest persistence |
| V119 | `source_index_bootstrap_runs` | Additive bootstrap run trail (PR #294) |
| Deploy `EXPECT_HEAD` | **119** | RO **snapshot** copy of live production DB at deploy time |
| Workspace DB | auto-migrates to **121** | RW staging/manifest tables via `ensure_workspace_db()` |

## Dual-DB architecture

```text
RO snapshot (mcp-snapshot)     RW workspace (mcp-workspace)
─────────────────────────     ────────────────────────────
Bind-mounted read-only        Writable mount for staging/manifest
MAX(schema_migrations)=119      MAX(schema_migrations)=121 (auto on start)
Construction/source reads       pa_* staging, manifest refresh, output workspace
```

The internet-facing MCP container **never** mounts the live production DB writable. Operator deploy
(`01-deploy-pr15.sh`) refreshes the RO snapshot from live at the **current production head** (119 at
PR-15 closeout) without applying new migrations to production. The workspace DB is a separate file under
`app-support/mcp-workspace/db/` and is migrated to head on container start (`ensure_workspace_db()` in
`src/hb_assistant/store/workspace.py`).

This is intentional: snapshot refresh is a **copy**, not a migration event; workspace schema must match
repo head for manifest V120/V121 tables.

## Terminology (avoid conflation)

| Label | Example | What it is |
|-------|---------|------------|
| `schema_migrations` version | 119 / 121 | SQLite migrator applied version per DB file |
| `manifest_version` | 7 | Client tool manifest revision counter |
| Operator “R4” | manifest refresh round | Human runbook label, not a schema version |
| `manifest_schema_version` | 1 | Manifest JSON payload contract |

## Operator verification

After deploy, confirm **both** heads:

```sh
# RO snapshot (expect deploy EXPECT_HEAD, typically 119 at PR-15)
# RW workspace (expect LATEST_SCHEMA_VERSION, 121)
```

See patched `01-deploy-pr15.sh` step 3b and `03-manifest-verify-pr15.sh` for automated prints.

## Residual risk

- Production live DB migration to 121 is a **separate** operator decision (out of request path).
- Image-byte attestation still requires `HB_RUNTIME_COMMIT` on NAS (F-002 `exact_unverified_stamp`).