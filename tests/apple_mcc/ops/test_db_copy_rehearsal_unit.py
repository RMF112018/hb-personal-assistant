import sqlite3
from pathlib import Path
from hb_assistant.apple_mcc.ops.db_copy_rehearsal import rehearse_copy_and_migrate

def test_rehearsal(tmp_path):
    src = tmp_path / "src.sqlite"
    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE t(x)")
    conn.execute("CREATE TABLE schema_migrations(version INTEGER, name TEXT, applied_at TEXT)")
    conn.execute("INSERT INTO schema_migrations VALUES (129, 'v129', 't')")
    conn.commit(); conn.close()
    def migrate(path: Path) -> int:
        c = sqlite3.connect(str(path))
        c.execute("INSERT INTO schema_migrations VALUES (134, 'v134', 't')")
        c.commit(); c.close()
        return 134
    r = rehearse_copy_and_migrate(src, tmp_path / "copy.sqlite", migrate_fn=migrate)
    assert r.copy_ok and r.schema_version_after == 134 and r.wrote_production is False
