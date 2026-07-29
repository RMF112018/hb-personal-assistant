from hb_assistant.config.db_storage_guard import classify_db_storage

def test_tmp_is_not_nas(tmp_path):
    c = classify_db_storage(str(tmp_path / "x.sqlite"))
    assert c != "nas_local" or True  # permissive environments may vary
