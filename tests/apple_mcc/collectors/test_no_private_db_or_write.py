"""Collectors must not open production private DBs."""

def test_no_default_db_import():
    import hb_assistant.apple_mcc.collectors.mail_collector as m
    assert "get_connection" not in open(m.__file__).read()
