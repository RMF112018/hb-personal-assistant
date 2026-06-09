# 03 — Graph Drive Item Normalization and Indexing

## Objective

Wire Graph `lastModifiedBy` through the drive item normalization/indexing path so the local DB stores raw modified-by operational metadata for SharePoint/OneDrive files.

## Required implementation

Update the Graph drive item normalizer/indexer to capture:

- `lastModifiedDateTime` → existing modified timestamp field;
- `lastModifiedBy.user.displayName` → modified-by display name;
- `lastModifiedBy.user.id` → modified-by user ID;
- `lastModifiedBy.user.email` or UPN if available → modified-by email/UPN field;
- `lastModifiedBy.application.displayName` → application display name;
- raw `lastModifiedBy` object → JSON field if added by Prompt 02.

Also verify/ensure capture of:

- project reference from source location or detected project field;
- folder/path from parent reference path or folder metadata;
- file name from drive item `name`;
- modified date/time from Graph `lastModifiedDateTime`.

## Normalization behavior

Handle all of these safely:

1. `lastModifiedBy` missing entirely.
2. `lastModifiedBy.user` present.
3. `lastModifiedBy.application` present.
4. `displayName` missing.
5. `email` missing.
6. unexpected keys present.
7. nested identity object contains non-string values.

Do not crash indexing on malformed identity data. Normalize to strings or NULL.

## Field priority

If both user and application are present:

- store user fields in user columns;
- store application display name in application column;
- preserve raw JSON if schema supports it.

If only application is present, display name may remain NULL but application display name should persist.

## Tests required

Add/extend normalizer/indexer tests:

1. complete `lastModifiedBy.user` fixture persists all fields;
2. application-only fixture persists application field;
3. missing field stores NULLs;
4. modified timestamp remains captured;
5. file name/path/project fields still captured;
6. idempotent re-index updates modified-by metadata;
7. fixture evidence is redacted/synthetic only.

## Live validation preparation

Create a safe DB copy and, if a Graph dry-run/index command exists, run it against a small bounded set.

Do not print raw file names or raw user names in terminal evidence. Use counts only.

Suggested safe live probe after indexing:

```bash
python - <<'PY'
import sqlite3, os
db = os.environ.get("DB")
if not db:
    raise SystemExit("Set DB to a safe DB copy path.")
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
targets = [c for c in cols if "modified_by" in c.lower() or "last_modified_by" in c.lower()]
print(f"modified_by_columns|{targets}")

for c in targets:
    count = con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {c} IS NOT NULL AND length(CAST({c} AS TEXT)) > 0"
    ).fetchone()[0]
    print(f"{c}|nonempty|{count}")

con.close()
PY
```

## Commit behavior

Commit coherent normalizer/indexer changes and tests.

Suggested commit message:

```text
feat(graph-files): map Graph lastModifiedBy into drive item index
```
