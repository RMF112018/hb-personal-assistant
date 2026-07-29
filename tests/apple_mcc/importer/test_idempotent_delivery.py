from hb_assistant.apple_mcc.importer.batch import import_batch
import sqlite3

def test_empty_batch_idempotent(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "t.sqlite"))
    r = import_batch(conn, [], import_one=lambda c, i: None)
    assert r["accepted"] == 0
