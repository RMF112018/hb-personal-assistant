from hb_assistant.apple_mcc.mail.fidelity import FidelityClass, classify_fidelity

def test_full_mime():
    assert classify_fidelity(has_raw_eml=True, body_text=None, body_html=None, preview=None) is FidelityClass.FULL_MIME
