from pathlib import Path
from hb_assistant.apple_mcc.mail.mime_parser import extract_bodies, parse_eml_bytes

def test_plain_and_multipart():
    root = Path("tests/fixtures/apple_mcc/mail")
    plain = parse_eml_bytes((root / "plain.eml").read_bytes())
    bodies = extract_bodies(plain)
    assert bodies["text"] and "Hello" in bodies["text"]
    multi = parse_eml_bytes((root / "multipart.eml").read_bytes())
    mb = extract_bodies(multi)
    assert mb["text"] and mb["html"]
