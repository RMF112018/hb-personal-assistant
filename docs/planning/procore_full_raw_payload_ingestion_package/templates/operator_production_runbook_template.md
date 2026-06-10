# Operator production runbook template

Update this after implementation. Do not run production mutation during implementation unless Bobby explicitly authorizes it.

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

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DB="/tmp/hb-prod-before-procore-full-raw-$TS.sqlite"

python - <<PY
import sqlite3
from pathlib import Path
src = Path("$PROD_DB")
dst = Path("$BACKUP_DB")
with sqlite3.connect(src) as source, sqlite3.connect(dst) as backup:
    source.backup(backup)
print(f"backup_created={dst}")
PY

shasum -a 256 "$PROD_DB" "$BACKUP_DB"

hb-assistant procore auth status --json
hb-assistant procore projects list --json
hb-assistant procore live endpoints ledger --json

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

hb-assistant procore analytics structured-counts \
  --db "$PROD_DB" \
  --json

sqlite3 "$PROD_DB" < docs/planning/procore_full_raw_payload_ingestion_package/templates/full_raw_payload_validation_sql.sql
```
