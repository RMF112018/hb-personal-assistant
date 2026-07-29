from hb_assistant.apple_mcc.identity.contact_revision import contact_linkage_id

def test_unmatched():
    assert len(contact_linkage_id("ab"*32, None, "unmatched")) == 64
