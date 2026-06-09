# 06 — Live DB Proof and Backfill Plan

## Objective

Prove the implementation against a safe DB copy and define how existing rows get populated.

This prompt may create temporary DB copies and temp output files. Do not mutate production DB unless Bobby explicitly approves.

## Required setup

Create a DB copy:

```bash
python - <<'PY'
import shutil
from pathlib import Path
from hb_assistant.config.path_policy import PathPolicy

src = PathPolicy().get_db_path()
dst = Path("/tmp/hb_graph_drive_modified_by_proof.sqlite")
shutil.copy2(src, dst)
print(f"source|{src}")
print(f"copy|{dst}")
PY

export DB=/tmp/hb_graph_drive_modified_by_proof.sqlite
```

## Required validation

1. Confirm schema columns exist on the DB copy.
2. Run the bounded Graph files/drive indexing command if available.
3. Confirm modified-by coverage counts increased or are nonzero if Graph data supplies the field.
4. Confirm project/folder/file/modified timestamp coverage still exists.
5. Confirm re-running is idempotent.
6. Confirm no source/content writeback occurs.
7. Confirm safe coverage output emits no raw values.

## Safe coverage script

Use actual table/column names from repo truth.

```bash
python - <<'PY'
import sqlite3, os

db = os.environ["DB"]
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

candidate_tables = [
    "construction_drive_items",
    "construction_drive_item_inventory",
    "drive_items",
]

for table in candidate_tables:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if not exists:
        continue

    print(f"table|{table}")
    print(f"rows|{con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")

    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    interesting = [
        c for c in cols
        if any(x in c.lower() for x in ["project", "path", "name", "modified", "by"])
    ]

    for c in interesting:
        try:
            nonempty = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {c} IS NOT NULL AND length(CAST({c} AS TEXT)) > 0"
            ).fetchone()[0]
            print(f"{c}|nonempty|{nonempty}")
        except sqlite3.OperationalError as exc:
            print(f"{c}|error|{type(exc).__name__}")

con.close()
PY
```

## Backfill decision

Determine and document one of:

1. Re-running the existing Graph drive-item indexer backfills modified-by fields.
2. A dedicated backfill command is required.
3. Backfill is not possible until the next live Graph refresh.
4. Graph tenant/API does not supply modified-by fields for the available items.

If a backfill command is required, implement only if scoped and safe. Otherwise document the reindex procedure.

## Evidence doc

Create or update a redacted evidence file only if repo conventions require it.

Evidence must include:

- DB copy path, not production DB mutation;
- table/column coverage counts;
- indexer command names;
- idempotency summary;
- no-writeback statement;
- no raw-values-emitted statement.

## Commit behavior

If only live validation is performed and no docs are changed, no commit is needed.

If docs/evidence are updated, commit them.

Suggested commit message:

```text
docs(graph-files): record modified-by metadata validation
```
