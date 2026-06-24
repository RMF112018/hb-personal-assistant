"""Schedule quality normalization helpers."""

from __future__ import annotations

from decimal import Decimal

from hb_assistant.construction.analytics.schedule_quality_normalization import (
    normalize_lag_days,
    normalize_lag_result,
    normalize_relationship_type,
    relationship_type_distribution,
)


def test_normalize_relationship_type_labels() -> None:
    assert normalize_relationship_type("Finish to Start") == "FS"
    assert normalize_relationship_type("Finish to Finish") == "FF"
    assert normalize_relationship_type("Start to Start") == "SS"
    assert normalize_relationship_type("Start to Finish") == "SF"
    assert normalize_relationship_type("fs") == "FS"


def test_twnu18_relationship_distribution() -> None:
    rels = (
        [{"relationship_type": "Finish to Start"}] * 2235
        + [{"relationship_type": "Finish to Finish"}] * 1357
        + [{"relationship_type": "Start to Start"}] * 125
        + [{"relationship_type": "Start to Finish"}] * 1
    )
    dist = relationship_type_distribution(rels)
    assert dist["total"] == 3718
    assert dist["FS"] == 2235
    assert dist["FF"] == 1357
    assert dist["SS"] == 125
    assert dist["SF"] == 1
    assert dist["non_fs_count"] == 1483


def test_normalize_lag_days_converts_source_units() -> None:
    assert normalize_lag_days(48, "hour") == Decimal("6")
    assert normalize_lag_days(360, "hour") == Decimal("45")
    assert normalize_lag_days(4800, "minute_tenth") == Decimal("1")
    assert normalize_lag_days(-16, "hour") == Decimal("-2")


def test_normalize_lag_result_classifies_known_assumed_and_unparseable() -> None:
    known = normalize_lag_result("48", "hour")
    assert known.normalized_days == Decimal("6")
    assert known.source_unit_label == "hour"
    assert known.conversion_status == "known_unit"

    missing = normalize_lag_result("12", None)
    assert missing.normalized_days == Decimal("12")
    assert missing.source_unit_label is None
    assert missing.conversion_status == "assumed_days"

    unknown = normalize_lag_result("7.5", "fortnight")
    assert unknown.normalized_days == Decimal("7.5")
    assert unknown.source_unit_label == "fortnight"
    assert unknown.conversion_status == "assumed_days"

    blank = normalize_lag_result("", "hour")
    assert blank.normalized_days is None
    assert blank.conversion_status == "unparseable"

    invalid = normalize_lag_result("not-a-number", "hour")
    assert invalid.normalized_days is None
    assert invalid.conversion_status == "unparseable"
