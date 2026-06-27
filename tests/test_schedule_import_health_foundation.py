"""Schedule import health foundation tests."""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
try:
    from fastapi.testclient import TestClient
except RuntimeError as exc:  # pragma: no cover - environment guard
    pytest.skip(str(exc), allow_module_level=True)

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.schedule_xml_parser import parse_pmxml_package_bytes
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _baseline_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <ObjectId>100</ObjectId>
    <Id>CUR</Id>
    <Name>Current Schedule</Name>
    <DataDate>2026-06-01</DataDate>
    <CurrentBaselineProjectObjectId>200</CurrentBaselineProjectObjectId>
  </Project>
  <WBS><ObjectId>W1</ObjectId><Code>ROOT</Code><Name>Root</Name></WBS>
  <Activity>
    <ObjectId>A1O</ObjectId><Id>A1</Id><Name>Start Work</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>2026-06-01</PlannedStartDate>
    <PlannedFinishDate>2026-06-05</PlannedFinishDate>
    <UDF><UDFType>Risk</UDFType><UDFValue>Low</UDFValue></UDF>
  </Activity>
  <Activity>
    <ObjectId>A2O</ObjectId><Id>A2</Id><Name>Finish Work</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>2026-06-06</PlannedStartDate>
    <PlannedFinishDate>2026-06-10</PlannedFinishDate>
  </Activity>
  <Relationship>
    <ObjectId>R1</ObjectId><PredecessorActivityObjectId>A1O</PredecessorActivityObjectId>
    <SuccessorActivityObjectId>A2O</SuccessorActivityObjectId><Type>FS</Type>
  </Relationship>
  <BaselineProject>
    <ObjectId>200</ObjectId>
    <Id>BL1</Id>
    <Name>Approved Baseline</Name>
    <OriginalProjectObjectId>100</OriginalProjectObjectId>
    <DataDate>2026-05-01</DataDate>
    <WBS><ObjectId>BW1</ObjectId><Code>ROOT</Code><Name>Root</Name></WBS>
    <Activity>
      <ObjectId>BA1O</ObjectId><Id>A1</Id><Name>Start Work</Name>
      <WBSObjectId>BW1</WBSObjectId><PlannedStartDate>2026-05-01</PlannedStartDate>
      <PlannedFinishDate>2026-05-05</PlannedFinishDate>
      <UDF><UDFType>BaselineFlag</UDFType><UDFValue>Y</UDFValue></UDF>
    </Activity>
    <Activity>
      <ObjectId>BA2O</ObjectId><Id>A2</Id><Name>Finish Work</Name>
      <WBSObjectId>BW1</WBSObjectId><PlannedStartDate>2026-05-06</PlannedStartDate>
      <PlannedFinishDate>2026-05-10</PlannedFinishDate>
    </Activity>
    <Relationship>
      <ObjectId>BR1</ObjectId><PredecessorActivityObjectId>BA1O</PredecessorActivityObjectId>
      <SuccessorActivityObjectId>BA2O</SuccessorActivityObjectId><Type>FS</Type>
    </Relationship>
  </BaselineProject>
</APIBusinessObjects>
"""


def _zip_payload() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("schedule.xml", _baseline_xml())
        zf.writestr("notes.txt", "ignored")
    return buf.getvalue()


def _companion_current_xml(*, project_name: str = "DEMO") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <UDFType><ObjectId>U1</ObjectId><Title>Install Note</Title><DataType>Text</DataType></UDFType>
  <Project>
    <ObjectId>1</ObjectId>
    <Id>DEMO</Id>
    <Name>{project_name}</Name>
    <DataDate>2026-06-01 08:00</DataDate>
    <PlannedStartDate>2026-01-01 08:00</PlannedStartDate>
    <ScheduledFinishDate>2026-12-31 17:00</ScheduledFinishDate>
    <CurrentBaselineProjectObjectId>BL100</CurrentBaselineProjectObjectId>
  </Project>
  <WBS><ObjectId>W1</ObjectId><Code>wbs1</Code><Name>WBS Root</Name></WBS>
  <Activity>
    <ObjectId>A1000O</ObjectId><Id>A1000</Id><Name>Driving Task</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>2026-02-01 08:00</PlannedStartDate>
    <PlannedFinishDate>2026-02-05 17:00</PlannedFinishDate>
    <UDF><ObjectId>UV1</ObjectId><TypeObjectId>U1</TypeObjectId><TextValue>XML companion note</TextValue></UDF>
  </Activity>
  <Activity>
    <ObjectId>A1010O</ObjectId><Id>A1010</Id><Name>Float Task</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>2026-03-01 08:00</PlannedStartDate>
    <PlannedFinishDate>2026-03-10 17:00</PlannedFinishDate>
  </Activity>
  <Relationship>
    <ObjectId>XR1</ObjectId><PredecessorActivityObjectId>A1000O</PredecessorActivityObjectId>
    <SuccessorActivityObjectId>A1010O</SuccessorActivityObjectId><Type>FS</Type><Lag>0</Lag><LagUnit>hour</LagUnit>
  </Relationship>
  <BaselineProject>
    <ObjectId>BL100</ObjectId><Id>BL1</Id><Name>Approved Baseline</Name>
    <OriginalProjectObjectId>1</OriginalProjectObjectId><DataDate>2026-05-01</DataDate>
    <Activity><ObjectId>BA1000O</ObjectId><Id>A1000</Id><Name>Driving Task</Name></Activity>
  </BaselineProject>
</APIBusinessObjects>
""".encode()


def _different_current_xml_same_project_name() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <ObjectId>1</ObjectId>
    <Id>DEMO</Id>
    <Name>DEMO</Name>
    <DataDate>2026-06-01 08:00</DataDate>
  </Project>
  <Activity><ObjectId>B2000O</ObjectId><Id>B2000</Id><Name>Different Task</Name></Activity>
</APIBusinessObjects>
"""


def _unified_zip_payload(xml: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("primary.xer", XER_FIXTURE.read_bytes())
        zf.writestr("companion.xml", xml or _companion_current_xml())
    return buf.getvalue()


def _twn_style_xer(activity_count: int = 1507) -> bytes:
    rows = [
        "ERMHDR\t18.8\t2026-06-22\tProject\tadmin\tdbxDatabaseNoName\tProjectMgr\tUSD",
        "%T\tPROJECT",
        "%F\tproj_id\tproj_short_name\tcritical_path_type\tcritical_drtn_hr_cnt\tuse_project_baseline_flag\tplan_start_date\tplan_end_date\tadd_date",
        "%R\t1071\tTWNU19\tCP_Drtn\t0\tN\t2026-01-01 08:00\t2026-12-31 17:00\t2026-06-23 08:00",
        "%T\tCALENDAR",
        "%F\tclndr_id\tclndr_name\tday_hr_cnt",
        "%R\t100\tStandard\t8",
        "%T\tPROJWBS",
        "%F\twbs_id\tproj_id\tparent_wbs_id\twbs_short_name\twbs_name",
        "%R\t10\t1071\t\twbs1\tWBS Root",
        "%T\tTASK",
        "%F\ttask_id\tproj_id\twbs_id\tclndr_id\ttask_code\ttask_name\tstatus_code\ttask_type\ttotal_float_hr_cnt\tfree_float_hr_cnt\tearly_start_date\tearly_end_date\tlate_start_date\tlate_end_date\tact_start_date\tact_end_date\ttarget_drtn_hr_cnt\tremain_drtn_hr_cnt\tphys_complete_pct\tdriving_path_flag\tcrt_path_num\tfloat_path\tfloat_path_order",
    ]
    rows.extend(
        "\t".join(
            [
                "%R",
                str(200000 + idx),
                "1071",
                "10",
                "100",
                f"TW{idx:04d}",
                f"TWN Activity {idx:04d}",
                "TK_Active",
                "TT_Task",
                "0",
                "0",
                "2026-06-23 08:00",
                "2026-06-23 17:00",
                "2026-06-23 08:00",
                "2026-06-23 17:00",
                "",
                "",
                "8",
                "8",
                "0",
                "N",
                "0",
                "0",
                "0",
            ]
        )
        for idx in range(1, activity_count + 1)
    )
    return ("\n".join(rows) + "\n").encode()


def _twn_style_pmxml(activity_count: int = 1507) -> bytes:
    activities = "\n".join(
        f"""
    <Activity>
      <ObjectId>PX{idx:04d}</ObjectId><Id>TW{idx:04d}</Id><Name>TWN Activity {idx:04d}</Name>
      <PlannedStartDate>2026-06-23T08:00:00</PlannedStartDate>
      <PlannedFinishDate>2026-06-23T17:00:00</PlannedFinishDate>
    </Activity>"""
        for idx in range(1, activity_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <ObjectId>1071XML</ObjectId>
    <Id>1071</Id>
    <Name>Tropical World Nursery - U19 06/23/26</Name>
    <DataDate>2026-06-23T08:00:00</DataDate>
{activities}
  </Project>
  <BaselineProject>
    <ObjectId>BL1</ObjectId><Id>BL1</Id><Name>Baseline One</Name>
    <OriginalProjectObjectId>1071XML</OriginalProjectObjectId><DataDate>2026-05-23</DataDate>
    <Activity><ObjectId>BL1A</ObjectId><Id>TW0001</Id><Name>TWN Activity 0001</Name></Activity>
  </BaselineProject>
  <BaselineProject>
    <ObjectId>BL2</ObjectId><Id>BL2</Id><Name>Baseline Two</Name>
    <OriginalProjectObjectId>1071XML</OriginalProjectObjectId><DataDate>2026-06-01</DataDate>
    <Activity><ObjectId>BL2A</ObjectId><Id>TW0002</Id><Name>TWN Activity 0002</Name></Activity>
  </BaselineProject>
</APIBusinessObjects>
""".encode()


def _twn_style_zip_payload() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("TWNU19.xer", _twn_style_xer())
        zf.writestr("Tropical World Nursery - U19 06-23-26.xml", _twn_style_pmxml())
    return buf.getvalue()


def _current_only_xml(*, object_id: str, project_id: str, name: str, data_date: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <ObjectId>{object_id}</ObjectId>
    <Id>{project_id}</Id>
    <Name>{name}</Name>
    <DataDate>{data_date}</DataDate>
  </Project>
  <WBS><ObjectId>W1</ObjectId><Code>ROOT</Code><Name>Root</Name></WBS>
  <Activity>
    <ObjectId>A1O</ObjectId><Id>A1</Id><Name>Start Work</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>{data_date}</PlannedStartDate>
    <PlannedFinishDate>{data_date}</PlannedFinishDate>
  </Activity>
</APIBusinessObjects>
""".encode()


def test_v75_schedule_import_health_tables_present(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION >= 75
    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "schedule_import_packages" in tables
    assert "schedule_baseline_projects" in tables
    assert "schedule_version_diff_facts" in tables


def test_v80_schedule_package_assembly_tables_present_and_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    migrator = SQLiteMigrator(db_path=str(db))
    assert migrator.apply() == LATEST_SCHEMA_VERSION >= 80
    assert migrator.apply() == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "schedule_package_field_lineage" in tables
        assert "schedule_package_equivalence_facts" in tables
        assert conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=80"
        ).fetchone()[0] == 1


def test_pmxml_package_parser_separates_current_and_baseline() -> None:
    entities = parse_pmxml_package_bytes(_baseline_xml(), source_file_id="xml-1")
    current = [e for e in entities if e.role == "current"]
    baselines = [e for e in entities if e.role == "baseline"]
    assert len(current) == 1
    assert len(baselines) == 1
    assert [a["activity_id"] for a in current[0].activities] == ["A1", "A2"]
    assert [a["activity_id"] for a in baselines[0].activities] == ["A1", "A2"]
    assert current[0].activities[0]["planned_start"] == "2026-06-01"
    assert baselines[0].activities[0]["planned_start"] == "2026-05-01"
    assert baselines[0].udf_values[0]["udf_type_name"] == "BaselineFlag"


def test_zip_xer_xml_current_companions_import_as_unified_schedule(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("unified-package.zip", _unified_zip_payload(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["assembly_mode"] == "unified_companion_package"
    assert body["activity_count"] == 2
    assert body["relationship_count"] == 1
    assert body["udf_count"] == 1
    assert body["source_format"] == "primavera_xer"
    assert body["equivalence_report"]["status"] == "compatible"
    assert body["capabilities"]["udfs"] == "available"

    commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={"import_id": body["import_id"], "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200
    committed = commit.json()
    svk = committed["schedule_version_key"]
    assert committed["baseline_project_count"] == 1

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        udf_rows = conn.execute(
            "SELECT activity_id, udf_type_name, udf_value FROM procore_ep_schedule_udf_values WHERE schedule_version_key=?",
            (svk,),
        ).fetchall()
        lineage = conn.execute(
            "SELECT field_family, source_format, merge_strategy FROM schedule_package_field_lineage WHERE schedule_version_key=?",
            (svk,),
        ).fetchall()
        equivalence = conn.execute(
            "SELECT is_equivalent, activity_overlap_ratio, relationship_overlap_ratio FROM schedule_package_equivalence_facts WHERE schedule_version_key=?",
            (svk,),
        ).fetchone()
    assert [dict(row) for row in udf_rows] == [
        {
            "activity_id": "A1000",
            "udf_type_name": "Install Note",
            "udf_value": "XML companion note",
        }
    ]
    assert any(
        row["field_family"] == "current_activities"
        and row["source_format"] == "primavera_xer"
        and row["merge_strategy"] == "primary_authoritative"
        for row in lineage
    )
    assert any(
        row["field_family"] == "current_udfs"
        and row["source_format"] == "primavera_pmxml"
        and row["merge_strategy"] == "companion_additive"
        for row in lineage
    )
    assert dict(equivalence) == {
        "is_equivalent": 1,
        "activity_overlap_ratio": "1.000000",
        "relationship_overlap_ratio": "1.000000",
    }


def test_zip_xer_xml_same_project_name_with_different_content_is_rejected(
    tmp_path: Path,
) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    resp = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={
            "file": (
                "mixed-package.zip",
                _unified_zip_payload(_different_current_xml_same_project_name()),
                "application/zip",
            )
        },
        data={"project_key": "tropical"},
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "schedule_package_multiple_current_candidates"
    assert detail["equivalence_report"]["status"] == "incompatible"
    assert detail["equivalence_facts"][0]["activity_overlap_ratio"] == "0.000000"


def test_twn_style_xer_pmxml_zip_with_same_data_date_and_activity_set_is_unified(
    tmp_path: Path,
) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("twnu19-package.zip", _twn_style_zip_payload(), "application/zip")},
        data={"project_key": "tropical"},
    )

    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["assembly_mode"] == "unified_companion_package"
    assert body["activity_count"] == 1507
    assert body["source_format"] == "primavera_xer"
    assert body["source_project_id"] == "1071"
    assert body["data_date"] == "2026-06-23 08:00"
    assert body["equivalence_report"]["status"] == "compatible"
    assert body["equivalence_report"]["equivalent_companion_count"] == 1
    assert len(body["baseline_project_candidates"]) == 2

    commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={"import_id": body["import_id"], "project_key": "tropical", "confirm": True},
    )

    assert commit.status_code == 200, commit.text
    committed = commit.json()
    svk = committed["schedule_version_key"]
    first_import_id = committed["import_id"]
    first_package_id = committed["package_id"]
    assert svk == "tropical|1071|2026-06-23 08:00"
    assert committed["baseline_project_count"] == 2

    with sqlite3.connect(db) as conn:
        lineage_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_package_field_lineage WHERE schedule_version_key=?",
            (svk,),
        ).fetchone()[0]
        equivalence = conn.execute(
            """
            SELECT is_equivalent, block_reason, activity_overlap_ratio, relationship_overlap_ratio,
                   primary_normalized_data_date, candidate_normalized_data_date
            FROM schedule_package_equivalence_facts
            WHERE schedule_version_key=?
            """,
            (svk,),
        ).fetchone()
        baseline_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_baseline_projects WHERE current_schedule_version_key=?",
            (svk,),
        ).fetchone()[0]

    assert lineage_count > 0
    assert equivalence == (1, None, "1.000000", "0.000000", "2026-06-23", "2026-06-23")
    assert baseline_count == 2

    duplicate_preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("twnu19-package.zip", _twn_style_zip_payload(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert duplicate_preview.status_code == 409
    assert duplicate_preview.json()["detail"]["code"] == "duplicate_schedule_version"

    supersede_preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("twnu19-package.zip", _twn_style_zip_payload(), "application/zip")},
        data={"project_key": "tropical", "confirm_supersede": "true"},
    )
    assert supersede_preview.status_code == 200, supersede_preview.text
    supersede_body = supersede_preview.json()
    assert supersede_body["import_id"] != first_import_id
    assert supersede_body["assembly_mode"] == "unified_companion_package"

    supersede_commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={
            "import_id": supersede_body["import_id"],
            "project_key": "tropical",
            "confirm": True,
            "confirm_supersede": True,
        },
    )
    assert supersede_commit.status_code == 200, supersede_commit.text
    superseded = supersede_commit.json()
    second_import_id = superseded["import_id"]
    second_package_id = superseded["package_id"]
    assert superseded["schedule_version_key"] == svk
    assert superseded["supersede_performed"] is True
    assert superseded["superseded_import_id"] == first_import_id
    assert second_package_id != first_package_id

    with sqlite3.connect(db) as conn:
        import_statuses = dict(
            conn.execute(
                """
                SELECT import_id, import_status
                FROM schedule_file_imports
                WHERE import_id IN (?, ?)
                """,
                (first_import_id, second_import_id),
            ).fetchall()
        )
        package_statuses = dict(
            conn.execute(
                """
                SELECT package_id, status
                FROM schedule_import_packages
                WHERE package_id IN (?, ?)
                """,
                (first_package_id, second_package_id),
            ).fetchall()
        )
        committed_package_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM schedule_import_packages
            WHERE selected_current_schedule_version_key=?
              AND status='committed'
            """,
            (svk,),
        ).fetchone()[0]
        superseded_package_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM schedule_import_packages
            WHERE selected_current_schedule_version_key=?
              AND status='superseded'
            """,
            (svk,),
        ).fetchone()[0]
        old_package_file_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_import_package_files WHERE package_id=?",
            (first_package_id,),
        ).fetchone()[0]
        active_activity_import_ids = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT import_id FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                (svk,),
            ).fetchall()
        }
        active_baseline_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_baseline_projects WHERE current_schedule_version_key=?",
            (svk,),
        ).fetchone()[0]
        new_lineage_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM schedule_package_field_lineage
            WHERE schedule_version_key=? AND package_id=? AND import_id=?
            """,
            (svk, second_package_id, second_import_id),
        ).fetchone()[0]
        new_equivalence_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM schedule_package_equivalence_facts
            WHERE schedule_version_key=? AND package_id=? AND import_id=?
            """,
            (svk, second_package_id, second_import_id),
        ).fetchone()[0]
        new_capability_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM schedule_source_capabilities
            WHERE schedule_version_key=? AND package_id=?
            """,
            (svk, second_package_id),
        ).fetchone()[0]

    assert import_statuses == {
        first_import_id: "superseded",
        second_import_id: "committed",
    }
    assert package_statuses == {
        first_package_id: "superseded",
        second_package_id: "committed",
    }
    assert committed_package_count == 1
    assert superseded_package_count >= 1
    assert old_package_file_count == 2
    assert active_activity_import_ids == {second_import_id}
    assert active_baseline_count == 2
    assert new_lineage_count > 0
    assert new_equivalence_count > 0
    assert new_capability_count > 0

    health = client.get(f"/api/schedules/versions/{svk}/health-data", headers=_operator())
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["import_package"]["package_id"] == second_package_id
    assert {row["package_id"] for row in health_body["package_lineage"]} == {second_package_id}
    assert {row["package_id"] for row in health_body["package_equivalence"]} == {second_package_id}


def test_zip_package_import_persists_baseline_and_health_data(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("schedule-package.zip", _zip_payload(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["package_mode"] == "zip_package"
    assert body["activity_count"] == 2
    assert body["baseline_project_candidates"][0]["project_id"] == "BL1"
    assert any(w["code"] == "unsupported_package_file_ignored" for w in body["warnings"])

    commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={"import_id": body["import_id"], "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200
    commit_body = commit.json()
    assert commit_body["baseline_project_count"] == 1
    assert commit_body["baseline_activity_count"] == 2

    svk = commit_body["schedule_version_key"]
    with sqlite3.connect(db) as conn:
        baseline_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_baseline_activities WHERE current_schedule_version_key=?",
            (svk,),
        ).fetchone()[0]
        current_count = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
            (svk,),
        ).fetchone()[0]
    assert current_count == 2
    assert baseline_count == 2

    health = client.get(f"/api/schedules/versions/{svk}/health-data", headers=_operator())
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["import_package"]["package_mode"] == "zip_package"
    assert health_body["baseline_projects"][0]["baseline_project_id"] == "BL1"
    assert health_body["deferred_domains"]["cost_schedule_correlation"] == "deferred"


def test_zip_rejects_path_traversal(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("../escape.xml", _baseline_xml())

    resp = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "schedule_zip_unsafe_path"


def test_zip_ignores_macosx_and_appledouble_members(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("schedule.xml", _baseline_xml())
        # macOS archive metadata: AppleDouble resource forks (named like a real .xml/.xer)
        # plus a __MACOSX/ sidecar must be ignored, not mis-parsed as schedule files.
        zf.writestr("__MACOSX/._schedule.xml", b"\x00\x05\x16\x07apple-double")
        zf.writestr("._schedule.xml", b"\x00\x05\x16\x07apple-double")

    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("schedule-package.zip", buf.getvalue(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["package_mode"] == "zip_package"
    assert [f["filename"] for f in body["files"]] == ["schedule.xml"]
    # No parse-failure noise referencing the macOS metadata members.
    noisy = [
        w
        for w in body["warnings"]
        if "MACOSX" in str(w.get("filename", "")) or str(w.get("filename", "")).startswith("._")
    ]
    assert noisy == []


def test_zip_blocks_multiple_non_equivalent_current_schedules(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr(
            "june.xml",
            _current_only_xml(object_id="100", project_id="CURJUN", name="June", data_date="2026-06-01"),
        )
        zf.writestr(
            "july.xml",
            _current_only_xml(object_id="200", project_id="CURJUL", name="July", data_date="2026-07-01"),
        )

    resp = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("ambiguous.zip", buf.getvalue(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "schedule_package_multiple_current_candidates"
    assert {c["data_date"][:10] for c in detail["candidates"]} == {"2026-06-01", "2026-07-01"}
