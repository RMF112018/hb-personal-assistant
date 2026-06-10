# Post-Merge Production Apply Runbook Template

Use only after review/merge.

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

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DB="/tmp/hb-prod-before-procore-projection-remediation-$TS.sqlite"

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

hb-assistant procore analytics projection-inventory --db "$PROD_DB" --json
hb-assistant procore analytics projection-reprocess --db "$PROD_DB" --apply --json
hb-assistant procore analytics projection-coverage --db "$PROD_DB" --json
```
