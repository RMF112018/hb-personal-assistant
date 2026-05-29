"""Phase 05 shared financial-normalizer / redaction-utility tests."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.financial import (
    attachment_path,
    build_amount_facts,
    company_entity,
    custom_field_policy,
    extract_currency_config,
    extract_wbs_cost_code,
    hash_identifier,
    html_to_text,
    mask_excerpt,
    parse_amount,
    person_hash_summary,
    summarize_text,
)


def test_parse_amount_preserves_negative_and_decimal_precision() -> None:
    # Negative + high-precision source strings survive byte-for-byte.
    assert parse_amount("-1234567.89012345") == "-1234567.89012345"
    assert parse_amount("0.000000000001") == "0.000000000001"
    assert parse_amount("100.00") == "100.00"  # trailing zeros preserved
    assert parse_amount("  -0.30 ") == "-0.30"  # trimmed
    assert parse_amount(42) == "42"
    assert parse_amount(None) is None
    assert parse_amount(True) is None  # bool is not an amount
    assert parse_amount("") is None


def test_extract_currency_config_top_level_and_nested() -> None:
    top = extract_currency_config({"currency_iso_code": "USD", "base_currency_iso_code": "USD"})
    assert top == {"currency_iso_code": "USD", "base_currency_iso_code": "USD"}
    nested = extract_currency_config(
        {"currency_configuration": {"currency_iso_code": "EUR", "exchange_rate": "1.0850"}}
    )
    assert nested["currency_iso_code"] == "EUR"
    assert nested["currency_exchange_rate"] == "1.0850"  # decimal-safe string


def test_extract_wbs_cost_code() -> None:
    out = extract_wbs_cost_code(
        {
            "wbs_code": {"id": 7, "flat_code": "03-3000", "description": "Concrete - Footings"},
            "cost_code": {"id": 9},
            "line_item_type_id": 4,
            "tax_code": {"id": 2},
        }
    )
    assert out == {
        "wbs_code_id": "7",
        "wbs_flat_code": "03-3000",
        "wbs_description": "Concrete - Footings",
        "cost_code_id": "9",
        "line_item_type_id": "4",
        "tax_code_id": "2",
    }


def test_mask_excerpt_masks_contact_pii() -> None:
    out = mask_excerpt("Email bob@example.test or call 555-123-4567, see https://x.test/a?b=c")
    assert out is not None
    assert "bob@example.test" not in out
    assert "555-123-4567" not in out
    assert "https://x.test" not in out
    assert "[email]" in out and "[phone]" in out and "[url]" in out


def test_summarize_text_strips_html_and_never_persists_raw() -> None:
    raw = "<p>Pour slab; contact <a href='mailto:bob@example.test'>bob@example.test</a></p>"
    summary = summarize_text(raw)
    assert summary is not None
    blob = json.dumps(summary)
    assert "<p>" not in blob and "</a>" not in blob  # no raw HTML
    assert "bob@example.test" not in blob  # email masked in excerpt
    assert summary["hash_prefix"] and isinstance(summary["length"], int)
    assert "[email]" in summary["excerpt"]
    assert html_to_text(raw).startswith("Pour slab")


def test_attachment_path_strips_signed_url_query() -> None:
    signed = "https://files.procore.test/prostore/abc.pdf?sig=SECRET&token=ABC123&company_id=5280"
    path = attachment_path(signed)
    assert path == "/prostore/abc.pdf"
    assert "SECRET" not in (path or "") and "token" not in (path or "")


def test_company_label_preserved_person_pii_hashed() -> None:
    company = company_entity({"id": 12, "name": "Acme Concrete LLC"}, kind="vendor")
    assert company == {"kind": "vendor", "id": 12, "name": "Acme Concrete LLC"}  # label kept
    person = person_hash_summary(
        {"id": 555, "name": "Synthetic Carl", "login": "carl@example.test"}
    )
    assert person is not None
    blob = json.dumps(person)
    assert "Synthetic Carl" not in blob and "carl@example.test" not in blob
    assert person["hash_prefix"] and person["id"] == 555
    # hash_identifier never echoes the raw value
    assert hash_identifier("carl@example.test") != "carl@example.test"


def test_custom_field_policy_preserves_decimal_hashes_string() -> None:
    out = custom_field_policy(
        {
            "cf_amount": {"data_type": "decimal", "value": "12.50"},
            "cf_note": {"data_type": "string", "value": "secret note bob@example.test"},
        }
    )
    fields = out["fields"]
    assert fields["cf_amount"]["value"] == "12.50"  # decimal preserved verbatim
    assert "value" not in fields["cf_note"]  # string not stored raw
    assert fields["cf_note"]["value_summary"]["hash_prefix"]
    assert "bob@example.test" not in json.dumps(out)


def test_build_amount_facts_skips_absent_and_preserves_decimal() -> None:
    canonical = {"original_contract_sum": "-1234567.89012345", "grand_total": None}
    facts = build_amount_facts(
        canonical,
        amount_columns=["original_contract_sum", "grand_total", "revised_contract_sum"],
        source_table="procore_financial_contracts",
    )
    assert len(facts) == 1
    assert facts[0] == {
        "amount_name": "original_contract_sum",
        "amount_value": "-1234567.89012345",
        "source_field_path": "procore_financial_contracts.original_contract_sum",
    }
