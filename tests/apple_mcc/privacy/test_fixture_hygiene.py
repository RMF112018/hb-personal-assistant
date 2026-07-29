from pathlib import Path

def test_fixtures_no_real_secrets():
    root = Path("tests/fixtures/apple_mcc")
    for p in root.rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            assert "password" not in text
