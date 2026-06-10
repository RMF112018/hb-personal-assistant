# Validation Command Checklist

```bash
cd /Users/bobbyfetting/hb-personal-assistant

python -m pip install -e .

PYTHONPATH="$PWD/src" python -m pytest tests/test_procore_full_raw_payload_ingestion.py -q
PYTHONPATH="$PWD/src" python -m pytest tests/test_procore_structured_analytics_foundation.py -q
PYTHONPATH="$PWD/src" python -m pytest tests/test_procore_endpoint_structured_projection_remediation.py -q

ruff check src/hb_assistant/procore src/hb_assistant/cli tests/test_procore_endpoint_structured_projection_remediation.py
mypy src/hb_assistant/procore src/hb_assistant/cli
```

DB-copy validation:

```bash
PROD_DB="$(python - <<'PY'
from hb_assistant.config.path_policy import PathPolicy
print(PathPolicy().get_db_path())
PY
)"
TS="$(date +%Y%m%d-%H%M%S)"
COPY_DB="/tmp/hb-procore-projection-remediation-$TS.sqlite"

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

hb-assistant procore analytics projection-inventory --db "$COPY_DB" --json
hb-assistant procore analytics projection-reprocess --db "$COPY_DB" --apply --json
hb-assistant procore analytics projection-coverage --db "$COPY_DB" --json
```
