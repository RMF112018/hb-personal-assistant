from construction_financial_review.common.safety import scan_text, safety_scan, FAIL_CATEGORIES


def test_detects_email_and_pem():
    f = scan_text("contact me at bob@example.com")
    assert f["email"] >= 1
    f2 = scan_text("-----BEGIN RSA PRIVATE KEY-----")
    assert f2["pem"] >= 1


def test_numeric_ids_do_not_false_positive_as_phone():
    # cost_code_id / wbs_code_id style pure-digit strings must NOT match the phone pattern.
    assert scan_text("cost_code_id 1007313329 wbs 2180120344")["phone"] == 0
    # wbs flat code with short dash groups must not match phone either.
    assert scan_text("1000.15-02-010.SUB")["phone"] == 0
    # a real separated phone DOES match.
    assert scan_text("call 561-555-1234")["phone"] >= 1


def test_raw_body_and_token_markers():
    assert scan_text('{"description_summary_json": "x"}')["raw_body_field"] >= 1
    assert scan_text("Authorization: Bearer abcdef0123456789")["bearer"] >= 1


def test_safety_scan_report_shape(tmp_path):
    clean = tmp_path / "clean.jsonl"
    clean.write_text('{"budget_code_key": "1000.15-16-110.SUB", "amount": "100.00"}\n', encoding="utf-8")
    report = safety_scan([clean])
    assert report["passed"] is True
    assert set(FAIL_CATEGORIES).issubset(set(report["findings"].keys()))
