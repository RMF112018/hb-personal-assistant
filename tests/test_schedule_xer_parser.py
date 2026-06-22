"""XER parser tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.schedule_file_parser import detect_source
from hb_assistant.construction.analytics.schedule_xer_parser import parse_xer_bytes

FIXTURE = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"
TWNU16 = Path(os.environ.get("HB_SCHEDULE_FIXTURE_XER", Path.home() / "Downloads/TWNU16.xer"))


def test_detect_xer_source() -> None:
    assert detect_source("demo.xer") == ("xer", "primavera_xer")


def test_parse_minimal_xer() -> None:
    bundle = parse_xer_bytes(FIXTURE.read_bytes())
    assert len(bundle.activities) == 2
    assert len(bundle.relationships) == 1
    driving = [a for a in bundle.activities if a.get("source_driving_path_flag")]
    assert len(driving) == 1
    assert driving[0]["activity_id"] == "A1000"
    assert bundle.source_capabilities["driving_path_count"] == 1
    assert bundle.source_capabilities["explicit_float_count"] == 2


@pytest.mark.manual
def test_parse_twnu16_xer_when_present() -> None:
    if not TWNU16.is_file():
        pytest.skip("TWNU16.xer not available")
    bundle = parse_xer_bytes(TWNU16.read_bytes())
    assert len(bundle.activities) == 1420
    assert len(bundle.relationships) == 3780
    assert bundle.source_capabilities["driving_path_count"] == 209
    assert bundle.source_capabilities["explicit_float_count"] == 900