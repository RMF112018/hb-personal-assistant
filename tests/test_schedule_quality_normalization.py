"""Schedule quality normalization helpers."""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_quality_normalization import (
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