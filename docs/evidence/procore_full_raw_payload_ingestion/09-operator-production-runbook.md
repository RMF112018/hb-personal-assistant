# 09 — Operator production runbook (post-merge)

Run only after merge, when Bobby intends to populate full raw payloads in the real
production DB. A live Procore GET is performed; all standard live gates apply. Back up
first; capture sha256 before/after.

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git fetch origin
git checkout main
git pull --ff-only origin main
python -m pip install -e .

PROD_DB="$(python - <<'PY'
from hb_assistant.config.path_policy import PathPolicy
print(PathPolicy().get_db_path())
PY
)"
echo "PROD_DB=$PROD_DB"

# 1) Back up + record sha (no migration needed; schema stays V46).
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DB="/tmp/hb-prod-before-procore-full-raw-$TS.sqlite"
python - <<PY
import sqlite3
from pathlib import Path
with sqlite3.connect(Path("$PROD_DB")) as s, sqlite3.connect(Path("$BACKUP_DB")) as d:
    s.backup(d)
print("backup_created=$BACKUP_DB")
PY
shasum -a 256 "$PROD_DB" "$BACKUP_DB"

# 2) Confirm auth + mapping, then run a gated live sync for the desired endpoint(s).
hb-assistant procore auth status --json
hb-assistant procore projects list --json

export PROJECT_KEY="REPLACE_WITH_PROJECT_KEY"
export HB_PROCORE_LIVE=1

HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project "$PROJECT_KEY" \
  --endpoint rfis \
  --apply \
  --sqlite-only \
  --confirm-live-get \
  --max-pages 1000 \
  --max-items 100000 \
  --json
# Receipt should show: full_raw_persistence_enabled=true, raw_payload_rows_written>0,
# structured_rows_written>0, raw_persist_error_count=0, ok=true.
# Repeat --endpoint for each desired endpoint family.

# 3) Project any pre-existing rows + verify; reprocess prefers full, falls back to legacy.
hb-assistant procore analytics reprocess --db "$PROD_DB" --apply --json
hb-assistant procore analytics structured-counts --db "$PROD_DB" --json
hb-assistant procore analytics coverage --db "$PROD_DB" --json

# 4) Validate source-quality distribution (no payload bodies printed).
python docs/planning/procore_full_raw_payload_ingestion_package/scripts/procore_full_raw_probe.py "$PROD_DB"
sqlite3 "$PROD_DB" < docs/planning/procore_full_raw_payload_ingestion_package/templates/full_raw_payload_validation_sql.sql

# 5) Optional rollback: restore the backup if anything looks wrong.
#   cp "$BACKUP_DB" "$PROD_DB"
```

Expectation: after live sync, synced endpoints flip from `redacted_legacy_projection`
(`raw_procore_payload_persisted=0`) to `live_full_payload` (`raw_procore_payload_persisted=1`),
and the `procore_raw_*` structured tables fill the business fields the redacted projection
left NULL. Legacy rows for endpoints not yet re-synced remain as a labelled fallback.
