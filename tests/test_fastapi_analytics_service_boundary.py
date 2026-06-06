"""Prompt 01 — FastAPI analytics service-boundary tests."""

from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.analytics import AnalyticsService
from hb_assistant.construction.analytics import service as analytics_service
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "BEGIN PRIVATE KEY",
    "access_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
)


def _migrated_db(tmp_path: Path) -> str:
    db = str(tmp_path / "analytics.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_service_instantiates_and_returns_metadata_only_payloads(tmp_path: Path) -> None:
    svc = AnalyticsService(db_path=_migrated_db(tmp_path))

    operations = svc.build_operations_summary()
    admin = svc.build_admin_confidence_summary()
    catalog = svc.build_metric_catalog_status()

    assert operations["surface"] == "analytics.operations_summary"
    assert admin["surface"] == "analytics.admin_confidence_summary"
    assert catalog["surface"] == "analytics.metric_catalog_status"
    assert operations["guardrails"]["read_only"] is True
    assert operations["guardrails"]["no_cli_shellout"] is True
    assert admin["readiness_overstated"] is False
    assert catalog["makes_determination"] is False

    serialized = json.dumps({"operations": operations, "admin": admin, "catalog": catalog}, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_service_uses_direct_python_boundary_not_cli_shellout() -> None:
    source = inspect.getsource(analytics_service)

    assert "subprocess" not in source
    assert "os.system" not in source
    assert "hb_assistant.cli" not in source
    assert "from hb_assistant.cli" not in source
    assert "import typer" not in source


def test_stale_schema_degrades_without_readiness_overstatement(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    svc = AnalyticsService(db_path=db)
    operations = svc.build_operations_summary()
    admin = svc.build_admin_confidence_summary()

    assert operations["schema_version"] == 5
    assert operations["readiness_overstated"] is False
    assert admin["schema_ready"] is False
    assert admin["readiness_overstated"] is False
    assert admin["status_counts"].get("unavailable", 0) >= 1


def test_operations_summary_reports_unavailable_when_no_project_read_model_data(
    tmp_path: Path,
) -> None:
    svc = AnalyticsService(db_path=_migrated_db(tmp_path))
    payload = svc.build_operations_summary()

    assert payload["project_count"] == 0
    unavailable = [
        metric for metric in payload["metrics"] if metric["status"] == "unavailable"
    ]
    assert unavailable
    assert all(metric["reason_code"] == "no_projects_with_procore_records" for metric in unavailable)


def test_catalog_status_loads_planning_catalog_without_rows(tmp_path: Path) -> None:
    svc = AnalyticsService(db_path=_migrated_db(tmp_path))
    payload = svc.build_metric_catalog_status()

    assert payload["status"] in {"available", "unavailable"}
    if payload["status"] == "available":
        assert "metrics" not in payload["value"]
        assert payload["value"]["metric_count"] == 135
