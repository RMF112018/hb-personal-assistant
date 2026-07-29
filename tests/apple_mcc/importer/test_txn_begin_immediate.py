import sqlite3
from hb_assistant.apple_mcc.importer.batch import begin_immediate

def test_begin_immediate(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "t.sqlite"))
    begin_immediate(conn)
    conn.commit()
