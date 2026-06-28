import os
import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
import hb_assistant.store.migrator as migrator_module

db_path = os.environ["HB_ASSISTANT_DB_PATH"]
evidence_dir = Path(os.environ["EVIDENCE_DIR"])
out_path = evidence_dir / "artifacts" / "apply-evidence-db-migrations-output.txt"

lines = []

def log(line: str) -> None:
    print(line)
    lines.append(line)

log(f"DB path: {db_path}")
log(f"Migrator module: {migrator_module.__file__}")
log(f"LATEST_SCHEMA_VERSION: {migrator_module.LATEST_SCHEMA_VERSION}")

migrator = SQLiteMigrator(db_path=db_path)

before = migrator.current_version()
log(f"Schema version before: {before}")

after = migrator.apply()
log(f"SQLiteMigrator.apply() returned: {after}")

final = migrator.current_version()
log(f"Schema version after: {final}")

conn = sqlite3.connect(db_path)
rows = conn.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name LIKE 'schedule_cpm%'
    ORDER BY name
    """
).fetchall()

log("")
log("schedule_cpm tables:")
for (name,) in rows:
    log(f"- {name}")

out_path.write_text("\n".join(lines) + "\n")
