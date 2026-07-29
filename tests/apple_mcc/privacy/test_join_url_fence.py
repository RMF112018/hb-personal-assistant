from hb_assistant.apple_mcc.privacy.join_url import fence_join_url

def test_join():
    assert fence_join_url("https://x", emit_external=True) == "[REDACTED_JOIN_URL]"
    assert fence_join_url("https://x", emit_external=False) == "https://x"
