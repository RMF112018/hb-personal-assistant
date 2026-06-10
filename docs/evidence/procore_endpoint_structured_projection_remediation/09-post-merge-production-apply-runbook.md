# 09 — Post-Merge Production Apply Runbook

After merging `fix/procore-endpoint-specific-structured-projections` to `main`, apply the
V47 schema and project existing full raw payloads into the endpoint-specific tables.

> No external writeback occurs at any step. No live Procore calls are made by the
> projection commands. Operate on the local analytical SQLite DB only.

## 1. Resolve and back up the production DB
```bash
PROD_DB="$(.venv/bin/python3.12 - <<'PY'
from hb_assistant.config.path_policy import PathPolicy
print(PathPolicy().get_db_path())
PY
)"
shasum -a 256 "$PROD_DB"
cp "$PROD_DB" "$PROD_DB.pre-v47.$(date +%Y%m%d-%H%M%S).bak"
```

## 2. Apply the V47 migration (additive; idempotent)
```bash
.venv/bin/python3.12 - <<PY
from hb_assistant.store.migrator import SQLiteMigrator
print("schema head:", SQLiteMigrator(db_path="$PROD_DB").apply())  # -> 47
PY
```

## 3. Project full raw payloads into endpoint-specific tables
```bash
hb-assistant procore analytics projection-reprocess --db "$PROD_DB" --apply --json
```
`--apply` requires `--db`; enforce mode fails closed (exit 3) if any payload contains a
business field path absent from the registry.

## 4. Verify completeness
```bash
hb-assistant procore analytics projection-audit --db "$PROD_DB" --json     # ok=true, unknown=0
hb-assistant procore analytics projection-coverage --db "$PROD_DB" --json  # sidecar % matrix
```

## Notes
- The production DB was already advanced to V47 + projected during this package's
  diagnosis (see `03-db-copy-validation.md`); on such a DB steps 2–3 are idempotent
  no-ops/refreshes.
- If `projection-audit` reports `unknown_business_field_paths > 0` after a future Procore
  schema change, regenerate the registry from a `/tmp` copy
  (`projection-inventory --emit-candidate`), review, and ship a new migration version —
  do not weaken the allow-list.
