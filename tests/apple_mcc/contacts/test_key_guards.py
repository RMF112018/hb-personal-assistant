from hb_assistant.apple_mcc.identity.contact_revision import container_locator_hash, contact_id_hash, contact_entity_id

def test_keys_len():
    c = container_locator_hash("iCloud")
    i = contact_id_hash(c, "CN")
    e = contact_entity_id(c, i)
    assert len(c) == len(i) == len(e) == 64
