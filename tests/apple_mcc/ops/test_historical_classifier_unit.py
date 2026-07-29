from hb_assistant.apple_mcc.ops.historical_empty_classifier import classify_row
from hb_assistant.apple_mcc.mail.empty_classification import EmptyDisposition

def test_hist():
    assert classify_row(byte_length=0, confirmed=True) is EmptyDisposition.CONFIRMED_EMPTY
