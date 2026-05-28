"""Phase 04 Prompt 08 — Daily log canonical normalization tests."""

from __future__ import annotations

import json

from hb_assistant.construction.fixtures.procore import DAILY_LOG_SAMPLE_PAYLOAD
from hb_assistant.procore.daily_log_selection import load_daily_log_selection
from hb_assistant.procore.normalizers.daily_log import (
    normalize_daily_log_payload_block,
    normalize_daily_log_section_item,
)

_FETCHED_AT = "2026-05-28T00:00:00+00:00"
_CORRELATION = "synthetic-corr-005"


def _normalize_all() -> dict[str, list[dict]]:
    selection = load_daily_log_selection()
    return normalize_daily_log_payload_block(
        DAILY_LOG_SAMPLE_PAYLOAD,
        selection_scope=selection,
        project_key="tropical",
        endpoint_id="list-daily-logs",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )


def test_normalize_emits_records_for_every_section_category() -> None:
    records = _normalize_all()
    # Every section that has items in the fixture should produce records.
    expected_categories = {
        "daily_log_counts",
        "daily_log_weather",
        "daily_log_manpower",
        "daily_log_dcr",
        "daily_log_delivery",
        "daily_log_notes",
        "daily_log_accident_review",
        "daily_log_injury_review",
        "daily_log_delay_review",
        "daily_log_safety_review",
    }
    assert set(records.keys()) == expected_categories


def test_normalize_per_category_counts_match_fixture_cardinality() -> None:
    records = _normalize_all()
    counts = {category: len(rows) for category, rows in records.items()}
    assert counts == {
        "daily_log_counts": 3,
        "daily_log_weather": 2,
        "daily_log_manpower": 3,
        "daily_log_dcr": 2,
        "daily_log_delivery": 2,
        "daily_log_notes": 2,
        "daily_log_accident_review": 1,
        "daily_log_injury_review": 1,
        "daily_log_delay_review": 1,
        "daily_log_safety_review": 1,
    }


def test_selected_section_records_are_low_risk_and_carry_canonical_fields() -> None:
    records = _normalize_all()
    counts_rows = records["daily_log_counts"]
    for row in counts_rows:
        assert row["review_required"] is False
        assert row["routing_reason"] == "default_low_risk"
        assert row["safety_route"] is False
        assert row["bucket"] == "selected"
        assert row["canonical_fields"]["count"] >= 1
        # Source `count` value is carried through, NOT a body summary.
        assert "body_summary" not in row


def test_review_only_notes_rows_are_review_required_with_body_summary() -> None:
    records = _normalize_all()
    notes_rows = records["daily_log_notes"]
    assert len(notes_rows) == 2
    for row in notes_rows:
        assert row["review_required"] is True
        assert row["routing_reason"] == "daily_log_review_only_section"
        assert row["safety_route"] is False
        assert row["bucket"] == "review_only"
        # Notes never carry the raw text — only a body summary.
        assert row["body_summary"]["type"] == "string"
        assert "hash_prefix" in row["body_summary"]
        assert "note" not in row["canonical_fields"]


def test_routed_to_review_rows_all_have_safety_route_and_hash_summary() -> None:
    records = _normalize_all()
    for category in (
        "daily_log_accident_review",
        "daily_log_injury_review",
        "daily_log_delay_review",
        "daily_log_safety_review",
    ):
        for row in records[category]:
            assert row["review_required"] is True
            assert row["safety_route"] is True
            assert row["routing_reason"].startswith("daily_log_routed_to_review:")
            assert row["bucket"] == "routed_to_review"
            assert row["body_summary"]["type"] == "string"
            assert "description" not in row["canonical_fields"]


def test_entity_stable_keys_are_unique_across_all_sections() -> None:
    records = _normalize_all()
    keys: list[str] = []
    for category_rows in records.values():
        keys.extend(row["entity_stable_key"] for row in category_rows)
    assert len(keys) == len(set(keys)), "entity_stable_key collision across daily log sections"


def test_parent_daily_log_stable_key_links_section_rows_back_to_parent() -> None:
    records = _normalize_all()
    for category, rows in records.items():
        for row in rows:
            assert row["parent_daily_log_stable_key"] in {
                "synthetic-dl-001",
                "synthetic-dl-002",
            }, f"unexpected parent key in {category}: {row['parent_daily_log_stable_key']!r}"


def test_normalize_serialized_output_never_carries_raw_section_text() -> None:
    records = _normalize_all()
    serialized = json.dumps(records)
    for raw_log in DAILY_LOG_SAMPLE_PAYLOAD:
        for key in (
            "notes_logs",
            "accident_logs",
            "injury_logs",
            "delay_logs",
            "safety_violation_logs",
        ):
            for item in raw_log.get(key, []):
                for text_field in ("description", "note", "narrative", "body", "comment"):
                    raw_text = item.get(text_field)
                    if isinstance(raw_text, str) and raw_text.strip():
                        assert raw_text not in serialized, (
                            f"raw {text_field!r} text from {key!r} leaked into serialized output"
                        )


def test_normalize_skips_sections_missing_from_payload() -> None:
    selection = load_daily_log_selection()
    minimal = [
        {
            "id": "synthetic-dl-empty",
            "log_date": "2026-05-27",
            # No section arrays present.
        }
    ]
    records = normalize_daily_log_payload_block(
        minimal,
        selection_scope=selection,
        project_key="tropical",
        endpoint_id="list-daily-logs",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert records == {}


def test_normalize_section_item_requires_id() -> None:
    selection = load_daily_log_selection()
    section = selection.selected_sections[0]
    try:
        normalize_daily_log_section_item(
            {},
            section=section,
            bucket="selected",
            parent_daily_log_stable_key="p",
            project_key="tropical",
            endpoint_id="list-daily-logs",
            correlation_id=_CORRELATION,
            fetched_at=_FETCHED_AT,
        )
    except ValueError:
        return
    raise AssertionError("missing-id section item should raise ValueError")
