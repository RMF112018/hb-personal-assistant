from hb_assistant.apple_mcc.privacy.fences import fence_raw_output

def test_fence():
    assert "[REDACTED_EMAIL]" in fence_raw_output("mail me at a@b.com please")
