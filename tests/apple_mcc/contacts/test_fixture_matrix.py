from pathlib import Path
from hb_assistant.apple_mcc.contacts.fetch import load_fixture

def test_fixtures():
    root = Path("tests/fixtures/apple_mcc/contacts")
    assert load_fixture(root / "person.json")["contact_type"] == "person"
    assert load_fixture(root / "org.json")["contact_type"] == "organization"
    assert len(load_fixture(root / "multi_phone.json")["phones"]) == 2
