from hb_assistant.apple_mcc.contacts.projection_registry import required_fields

def test_fields():
    assert "has_email" in required_fields()
