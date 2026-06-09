# 01 — Schema and Contract Audit

## Objective

Perform a deeper audit of the Graph drive item metadata contract, schema, DB reality, and storage path before implementation.

Do not modify code in this prompt.

## Required questions to answer

1. What Graph drive item fields are currently selected/requested?
2. Is `lastModifiedDateTime` captured and persisted?
3. Is `lastModifiedBy` requested or present in the raw Graph payload?
4. If present, is `lastModifiedBy` discarded by the normalizer?
5. Which DB table is canonical for drive item rows?
6. Which DB table, if any, stores raw Graph metadata JSON?
7. Which fields currently store:
   - project reference;
   - folder/path;
   - file name;
   - modified date/time?
8. Is there any existing redacted/raw split for file metadata?
9. Do evidence/docs intentionally redact file names and user names?
10. What migration strategy is safest?

## DB schema audit

Run safe schema probes only. Do not print raw row values.

```bash
python - <<'PY'
import sqlite3
from hb_assistant.config.path_policy import PathPolicy

db = PathPolicy().get_db_path()
print(f"db_path|{db}")

tables = [
    "construction_source_locations",
    "construction_drive_items",
    "construction_drive_item_inventory",
    "drive_items",
    "source_locations",
    "source_records",
    "source_links",
]

con = sqlite3.connect(db)
for t in tables:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (t,),
    ).fetchone()
    if not exists:
        print(f"\n{t}|MISSING")
        continue

    print(f"\n[{t}]")
    print(f"row_count|{con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    for row in con.execute(f"PRAGMA table_info({t})"):
        col = row[1]
        low = col.lower()
        flag = ""
        if any(x in low for x in ["project", "name", "path", "modified", "by", "user", "identity", "json", "url"]):
            flag = "  <-- relevant"
        print(f"{col}{flag}")

con.close()
PY
```

## Contract audit

Inspect the code that normalizes Graph drive item payloads.

Specifically determine whether the following Graph shape is handled:

```json
{
  "lastModifiedDateTime": "2026-06-09T12:34:56Z",
  "lastModifiedBy": {
    "user": {
      "displayName": "Jane Doe",
      "id": "...",
      "email": "jane@example.com"
    },
    "application": {
      "displayName": "Microsoft Office"
    }
  }
}
```

Do not assume the email field always exists. Graph identity sets vary by tenant/item.

## Required audit output

Produce:

1. exact current field mapping;
2. exact current missing fields;
3. candidate schema design;
4. recommended migration;
5. files that must change;
6. tests that must be added;
7. live validation plan;
8. evidence plan.

## Commit behavior

No commit in this prompt.
