# 05 — Health proof

## `/health` (viewer)

```sh
sudo HB_VIEWER_HEALTH_OK=1 sh scripts/health.sh
```

**Immediate post-start:** connection reset (container still starting) — expected race.

**After ~25s startup wait:** **HTTP 200**

| Field | Value |
|---|---|
| `schema_version` | 98 |
| `schema_ready` | true |
| `db_storage_class` | `nas_local` |
| `background_worker_mode` | `disabled` |
| `startup_migration_performed` | false |

Sanitized JSON captured in manual retry log: `json/health-admin-manual-sanitized.log` (health portion).

## Admin DB status

```sh
sudo HB_VIEWER_HEALTH_OK=1 HB_ADMIN_DB_STATUS=1 sh scripts/health.sh
```

**Script result:** **WARN** — curl word-split on `-H X-HB-UI-Role: admin` (`Could not resolve host: admin`).

**Manual operator curl (proof):**

```sh
curl -fsS -H "X-HB-UI-Role: admin" http://127.0.0.1:8000/api/admin/db/status
```

**HTTP 200** — metadata only; `table_count=505`, `view_count=2`, `schema_object_count=507`.

Follow-up: fix `health.sh` header quoting for `HB_ADMIN_DB_STATUS=1`.
