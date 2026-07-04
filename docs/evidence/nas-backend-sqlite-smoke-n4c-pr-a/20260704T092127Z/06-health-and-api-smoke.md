# 06 — Health and API smoke

All endpoints returned **200**. Captured JSON under `evidence/`.

## GET /health (viewer)

| Field | Value |
|---|---|
| `status` | `ok` |
| `schema_version` | **98** |
| `schema_expected` | **98** |
| `schema_ready` | **true** |
| `db_storage_class` | **`nas_local`** |
| `background_worker_mode` | **`disabled`** |
| `startup_migration_performed` | **`false`** |

Sanitized: no `resolved_db_path`, no uid/gid/mode on public health payload.

## GET /api/admin/schema/status (admin)

| Field | Value |
|---|---|
| `schema_version` | **98** |
| `schema_ready` | **true** |
| `table_count` | **505** |
| `view_count` | **2** |
| `schema_object_count` | **507** |

## GET /api/admin/db/status (admin)

Metadata only — posture fields including journal mode, busy timeout, file sizes; **no row contents or secrets**.

Notable: `foreign_keys=0` on read-only probe connection (non-blocking follow-up; see `00-closeout.md`).

## GET /api/environment

`live_reads.enable_live_reads=false`; live refresh disabled by default.

## GET /api/onboarding/readiness

No tokens, secrets, Graph, or Procore call material in response body.
