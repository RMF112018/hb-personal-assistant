"""MSP XML parser and sniff tests."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.schedule_file_parser import (
    detect_source,
    sniff_xml_source_format,
)
from hb_assistant.construction.analytics.schedule_msp_xml_parser import parse_msp_xml_bytes

MSP_ZIP = Path(
    os.environ.get(
        "HB_SCHEDULE_FIXTURE_MSP",
        Path.home() / "Documents/TWNU18.xml.zip",
    )
)
P6_FIXTURE = Path(__file__).parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"


def test_sniff_msp_namespace() -> None:
    if not MSP_ZIP.is_file():
        pytest.skip("MSP fixture zip not available")
    with zipfile.ZipFile(MSP_ZIP) as zf:
        data = zf.read("TWNU18.xml")
    assert sniff_xml_source_format(data) == "ms_project_xml"
    assert detect_source("TWNU18.xml", data=data) == ("xml", "ms_project_xml")


def test_sniff_p6_xml_defaults_to_pmxml() -> None:
    data = P6_FIXTURE.read_bytes()
    assert sniff_xml_source_format(data) == "primavera_pmxml"


def test_parse_msp_relationship_preserves_link_lag_minute_tenths() -> None:
    data = b"""<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project/2007">
  <Name>Lag Unit Test</Name>
  <UID>msp-lag-test</UID>
  <Tasks>
    <Task>
      <UID>1</UID>
      <ID>10</ID>
      <Name>Predecessor</Name>
    </Task>
    <Task>
      <UID>2</UID>
      <ID>20</ID>
      <Name>Successor</Name>
      <PredecessorLink>
        <PredecessorUID>1</PredecessorUID>
        <Type>1</Type>
        <LinkLag>4800</LinkLag>
      </PredecessorLink>
    </Task>
  </Tasks>
</Project>
"""
    bundle = parse_msp_xml_bytes(data)
    assert len(bundle.relationships) == 1
    rel = bundle.relationships[0]
    assert rel["predecessor_activity_id"] == "10"
    assert rel["successor_activity_id"] == "20"
    assert rel["relationship_type"] == "FS"
    assert rel["lag_value"] == "4800"
    assert rel["lag_unit"] == "minute_tenth"


@pytest.mark.manual
def test_parse_msp_twnu18_when_present() -> None:
    if not MSP_ZIP.is_file():
        pytest.skip("MSP fixture zip not available")
    with zipfile.ZipFile(MSP_ZIP) as zf:
        data = zf.read("TWNU18.xml")
    bundle = parse_msp_xml_bytes(data)
    assert len(bundle.activities) == 1378
    assert bundle.source_capabilities["explicit_float_count"] == 677
    assert bundle.source_capabilities["source_format"] == "ms_project_xml"
