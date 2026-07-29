from hb_assistant.apple_mcc.contacts.feature_flags import contacts_enabled
from hb_assistant.apple_mcc.contacts.fetch import fetch_contacts_or_empty

def test_disabled(monkeypatch):
    monkeypatch.setenv("APPLE_MCC_CONTACTS_ENABLED", "0")
    assert fetch_contacts_or_empty() == []
