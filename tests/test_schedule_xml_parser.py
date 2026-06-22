"""PMXML/XML schedule parser fixture tests (minimal + real P6 samples)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.schedule_xml_parser import parse_pmxml_bytes

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml"
DOWNLOADS_ZIP = Path("/Users/bobbyfetting/Downloads/schedule-xml-files.zip")

EXPECTED_SAMPLES = {
    "GMA.xml": {"activities": 189, "relationships": 282, "wbs": 24},
    "TWNU07.xml": {"activities": 1177, "relationships": 2658, "wbs": 135},
    "TWNU16.xml": {"activities": 1420, "relationships": 3780, "wbs": 188},
    "TWNU18.xml": {"activities": 1378, "relationships": 3718, "wbs": 188},
    "PGATM-B0-R2.xml": {"activities": 1081, "relationships": 1499, "wbs": 86},
    "CARETTABL.xml": {"activities": 2949, "relationships": 5191, "wbs": 221},
}


def test_parse_minimal_xml_fixture() -> None:
    data = (FIXTURE_DIR / "minimal_schedule.xml").read_bytes()
    bundle = parse_pmxml_bytes(data)
    assert len(bundle.activities) == 2
    assert bundle.activities[0]["activity_id"] == "A100"
    assert bundle.relationships
    assert bundle.wbs_nodes
    assert bundle.calendars


def test_parse_gma_real_sample() -> None:
    data = (FIXTURE_DIR / "gma_sample.xml").read_bytes()
    bundle = parse_pmxml_bytes(data)
    assert len(bundle.activities) == 189
    assert len(bundle.relationships) == 282
    assert len(bundle.wbs_nodes) == 24
    assert bundle.schedule_id == "GMA"
    assert bundle.data_date is not None

    assert bundle.schedule_options.get("compute_total_float_type")
    assert "Finish Float = Late Finish - Early Finish" in str(
        bundle.schedule_options.get("compute_total_float_type")
    )

    first = bundle.activities[0]
    assert first["activity_id"] == "BUY-ALBANY-EH1-1010"
    assert first["source_activity_object_id"] == "99508"
    assert first.get("planned_start")
    assert first.get("planned_finish")
    assert first.get("activity_status") == "Not Started"
    assert first.get("duration_original") == "40"
    assert first.get("remaining_early_finish")
    assert first.get("remaining_late_finish")
    assert first.get("derived_float_basis") == "remaining_late_finish_minus_remaining_early_finish"
    assert float(first.get("derived_total_float_days") or 0) > 0

    act_ids = {a["activity_id"] for a in bundle.activities}
    for rel in bundle.relationships[:20]:
        assert rel["predecessor_activity_id"] in act_ids
        assert rel["successor_activity_id"] in act_ids


@pytest.mark.parametrize("filename,expected", list(EXPECTED_SAMPLES.items()))
def test_parse_downloads_zip_samples(filename: str, expected: dict[str, int]) -> None:
    if not DOWNLOADS_ZIP.exists():
        pytest.skip("schedule-xml-files.zip not present in Downloads")
    with zipfile.ZipFile(DOWNLOADS_ZIP) as zf:
        try:
            data = zf.read(filename)
        except KeyError:
            pytest.skip(f"{filename} missing from zip")
    bundle = parse_pmxml_bytes(data)
    assert len(bundle.activities) == expected["activities"]
    assert len(bundle.relationships) == expected["relationships"]
    if expected["wbs"]:
        assert len(bundle.wbs_nodes) == expected["wbs"]

    act_ids = {a["activity_id"] for a in bundle.activities}
    unresolved = [
        r
        for r in bundle.relationships
        if r["predecessor_activity_id"] not in act_ids or r["successor_activity_id"] not in act_ids
    ]
    assert unresolved == []