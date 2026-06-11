# Validation Command Checklist

```bash
cd /Users/bobbyfetting/hb-personal-assistant

python -m pip install -e .

PYTHONPATH="$PWD/src" python -m pytest tests/test_email_calendar_full_raw_content_ingestion.py -q
PYTHONPATH="$PWD/src" python -m pytest tests/test_email_calendar_structured_projection_remediation.py -q
PYTHONPATH="$PWD/src" python -m pytest tests/test_email_calendar_projection_completeness.py -q

ruff check src/hb_assistant/construction/email src/hb_assistant/construction/calendar src/hb_assistant/construction/meeting_prep src/hb_assistant/cli tests/test_email_calendar_structured_projection_remediation.py
mypy src/hb_assistant/construction/email src/hb_assistant/construction/calendar src/hb_assistant/construction/meeting_prep src/hb_assistant/cli
```

DB-copy validation:

```bash
PROD_DB="$(python - <<'PY'
from hb_assistant.config.path_policy import PathPolicy
print(PathPolicy().get_db_path())
PY
)"
TS="$(date +%Y%m%d-%H%M%S)"
COPY_DB="/tmp/hb-email-calendar-structured-projection-$TS.sqlite"

python - <<PY
import sqlite3
from pathlib import Path
src = Path("$PROD_DB")
dst = Path("$COPY_DB")
with sqlite3.connect(src) as source, sqlite3.connect(dst) as backup:
    source.backup(backup)
print(dst)
PY

shasum -a 256 "$PROD_DB" "$COPY_DB"

python docs/planning/email_calendar_full_raw_content_ingestion_package/scripts/email_calendar_raw_projection_inventory.py   --db "$COPY_DB"   --out "/tmp/email-calendar-raw-field-inventory-$TS.csv"

hb-assistant email-calendar raw projection-inventory --db "$COPY_DB" --json
hb-assistant email-calendar raw projection-reprocess --db "$COPY_DB" --apply --json
hb-assistant email-calendar raw projection-coverage --db "$COPY_DB" --json
```

The package is not complete until projection coverage reports zero unmapped primary and nested business fields for every email/calendar source family with available raw rows.
