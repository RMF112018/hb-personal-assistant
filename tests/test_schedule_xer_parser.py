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


def test_parse_xer_preserves_target_dates_as_non_baseline() -> None:
    data = b"""ERMHDR\t18.8\t2026-06-22\tProject\tadmin\tdbxDatabaseNoName\tProjectMgr\tUSD
%T\tPROJECT
%F\tproj_id\tproj_short_name\tcritical_path_type\tcritical_drtn_hr_cnt\tuse_project_baseline_flag\tplan_start_date\tplan_end_date\tadd_date
%R\t1\tDEMO\tCP_Drtn\t0\tN\t2026-01-01 08:00\t2026-12-31 17:00\t2026-06-01 08:00
%T\tCALENDAR
%F\tclndr_id\tclndr_name\tday_hr_cnt
%R\t100\tStandard\t8
%T\tPROJWBS
%F\twbs_id\tproj_id\tparent_wbs_id\twbs_short_name\twbs_name
%R\t10\t1\t\twbs1\tWBS Root
%T\tTASK
%F\ttask_id\tproj_id\twbs_id\tclndr_id\ttask_code\ttask_name\tstatus_code\ttask_type\ttotal_float_hr_cnt\tfree_float_hr_cnt\tearly_start_date\tearly_end_date\tlate_start_date\tlate_end_date\tact_start_date\tact_end_date\ttarget_start_date\ttarget_end_date\ttarget_drtn_hr_cnt\tremain_drtn_hr_cnt\tphys_complete_pct\tdriving_path_flag
%R\t1001\t1\t10\t100\tA1000\tTarget Task\tTK_Active\tTT_Task\t0\t0\t2026-02-01 08:00\t2026-02-05 17:00\t2026-02-01 08:00\t2026-02-05 17:00\t\t\t2026-01-20 08:00\t2026-01-25 17:00\t40\t24\t50\tY
"""
    bundle = parse_xer_bytes(data)
    activity = bundle.activities[0]

    assert activity["target_start"] == "2026-01-20 08:00"
    assert activity["target_finish"] == "2026-01-25 17:00"
    assert activity.get("baseline_start") is None
    assert activity.get("baseline_finish") is None


@pytest.mark.manual
def test_parse_twnu16_xer_when_present() -> None:
    if not TWNU16.is_file():
        pytest.skip("TWNU16.xer not available")
    bundle = parse_xer_bytes(TWNU16.read_bytes())
    assert len(bundle.activities) == 1420
    assert len(bundle.relationships) == 3780
    assert bundle.source_capabilities["driving_path_count"] == 209
    assert bundle.source_capabilities["explicit_float_count"] == 900
