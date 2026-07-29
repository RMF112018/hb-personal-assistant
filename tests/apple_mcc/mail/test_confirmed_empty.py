from hb_assistant.apple_mcc.mail.empty_classification import EmptyDisposition, classify_empty

def test_confirmed():
    assert classify_empty(byte_length=0, provider_flags={"confirmed_empty": True}) is EmptyDisposition.CONFIRMED_EMPTY
