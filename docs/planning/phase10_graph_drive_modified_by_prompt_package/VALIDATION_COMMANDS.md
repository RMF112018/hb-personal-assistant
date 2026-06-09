# Validation Commands

Use these as a starting point. Adjust file paths and test names to repo truth.

## Branch checks

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
```

## Schema inspection

```bash
python - <<'PY'
import sqlite3
from hb_assistant.config.path_policy import PathPolicy

db = PathPolicy().get_db_path()
print(f"db_path|{db}")
con = sqlite3.connect(db)

for t in [
    "construction_source_locations",
    "construction_drive_items",
    "construction_drive_item_inventory",
    "drive_items",
    "source_locations",
    "source_records",
]:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (t,),
    ).fetchone()
    if not exists:
        print(f"{t}|MISSING")
        continue
    print(f"\n[{t}]")
    for row in con.execute(f"PRAGMA table_info({t})"):
        print(row[1])

con.close()
PY
```

## Targeted tests

```bash
python -m pytest tests -q -k "drive_item or graph_file or graph_files or source_location or migration"
ruff check <changed paths>
ruff format --check <changed paths>
mypy <changed modules>
```

## Safe coverage proof

```bash
export DB=/tmp/hb_graph_drive_modified_by_proof.sqlite

python - <<'PY'
import sqlite3, os

db = os.environ["DB"]
con = sqlite3.connect(db)

table = "construction_drive_items"
exists = con.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
    (table,),
).fetchone()

if not exists:
    print(f"{table}|MISSING")
    raise SystemExit(0)

cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
targets = [c for c in cols if any(x in c.lower() for x in ["project", "path", "name", "modified", "by"])]

print(f"rows|{con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")
for c in targets:
    count = con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {c} IS NOT NULL AND length(CAST({c} AS TEXT)) > 0"
    ).fetchone()[0]
    print(f"{c}|nonempty|{count}")

con.close()
PY
```
