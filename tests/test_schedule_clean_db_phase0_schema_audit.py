"""Schema audit tool tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.schedule_clean_db.schema_audit import build_schema_audit_report
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "audit.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_comparable_versions(db)
    return db


def test_discovers_schedule_tables_dynamically(tmp_path: Path) -> None:
    report = build_schema_audit_report(_db(tmp_path), project_key="tropical")
    tables = {row["table"] for row in report["discovered_by_heuristic"]}
    assert "schedule_file_imports" in tables
    assert "procore_ep_schedule_activities" in tables


def test_row_counts_for_seeded_fixture(tmp_path: Path) -> None:
    report = build_schema_audit_report(_db(tmp_path), project_key="tropical")
    imports = next(r for r in report["discovered_by_heuristic"] if r["table"] == "schedule_file_imports")
    assert imports["row_count_for_project"] == 2


def test_catalog_preserved(tmp_path: Path) -> None:
    report = build_schema_audit_report(_db(tmp_path), project_key="tropical")
    projects = next(r for r in report["discovered_by_heuristic"] if r["table"] == "procore_ep_projects")
    assert projects["preserve_catalog"] is True


def test_live_db_rejected_without_read_only_flag() -> None:
    live = PathPolicy().get_db_path()
    with pytest.raises(ValueError, match="live database"):
        build_schema_audit_report(live, project_key="tropical")


def test_required_expected_section_present(tmp_path: Path) -> None:
    report = build_schema_audit_report(_db(tmp_path), project_key="tropical")
    assert "required_expected_tables_missing_or_unclassified" in report
