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


def _msp_xml_tasks(tasks: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project/2007">
  <Name>MSP Source Fields Test</Name>
  <UID>msp-source-fields-test</UID>
  <Tasks>
{tasks}
  </Tasks>
</Project>
""".encode()


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
    data = _msp_xml_tasks(
        """
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
"""
    )
    bundle = parse_msp_xml_bytes(data)
    assert len(bundle.relationships) == 1
    rel = bundle.relationships[0]
    assert rel["predecessor_activity_id"] == "10"
    assert rel["successor_activity_id"] == "20"
    assert rel["relationship_type"] == "FS"
    assert rel["lag_value"] == "4800"
    assert rel["lag_unit"] == "minute_tenth"


def test_parse_msp_preserves_critical_and_slack_source_fields() -> None:
    data = _msp_xml_tasks(
        """
    <Task>
      <UID>1</UID>
      <ID>10</ID>
      <Name>Critical zero slack</Name>
      <Critical>1</Critical>
      <TotalSlack>0</TotalSlack>
      <FreeSlack>0</FreeSlack>
    </Task>
    <Task>
      <UID>2</UID>
      <ID>20</ID>
      <Name>Noncritical positive slack</Name>
      <Critical>0</Critical>
      <TotalSlack>960</TotalSlack>
      <FreeSlack>480</FreeSlack>
    </Task>
    <Task>
      <UID>3</UID>
      <ID>30</ID>
      <Name>Missing critical</Name>
      <TotalSlack>480</TotalSlack>
    </Task>
"""
    )
    bundle = parse_msp_xml_bytes(data)
    by_id = {activity["activity_id"]: activity for activity in bundle.activities}

    critical = by_id["10"]
    assert critical["source_critical_flag"] == 1
    assert critical["source_critical_flag_present"] is True
    assert critical["source_critical_raw"] == "1"
    assert critical["explicit_total_float_hours"] == "0.0"
    assert critical["explicit_total_float_days"] == "0.0"
    assert critical["explicit_free_float_hours"] == "0.0"
    assert critical["explicit_free_float_days"] == "0.0"

    noncritical = by_id["20"]
    assert noncritical["source_critical_flag"] == 0
    assert noncritical["source_critical_flag_present"] is True
    assert noncritical["source_critical_raw"] == "0"
    assert noncritical["explicit_total_float_hours"] == "16.0"
    assert noncritical["explicit_total_float_days"] == "2.0"
    assert noncritical["explicit_free_float_hours"] == "8.0"
    assert noncritical["explicit_free_float_days"] == "1.0"

    missing = by_id["30"]
    assert missing["source_critical_flag"] == 0
    assert missing["source_critical_flag_present"] is False
    assert missing["source_critical_raw"] is None
    assert missing["explicit_total_float_days"] == "1.0"


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
