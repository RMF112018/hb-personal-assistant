from hb_assistant.apple_mcc.privacy.fences import redact_phone

def test_phone():
    assert "[REDACTED_PHONE]" in redact_phone("call +1-555-0100 now")
