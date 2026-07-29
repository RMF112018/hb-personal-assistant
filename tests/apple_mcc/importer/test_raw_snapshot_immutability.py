from hb_assistant.apple_mcc.identity.email_revision import email_raw_snapshot_id, email_revision_key

def test_snap_from_rev():
    rev = email_revision_key("ab"*32, "cd"*32)
    assert email_raw_snapshot_id(rev) != rev
