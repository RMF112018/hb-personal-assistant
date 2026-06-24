"""P-C — ForecastGenerationRequestRepository tests (temp SQLite DB only)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.store.forecast_generation_request_repository import (
    ForecastGenerationRequestRepository,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _repo(td: str) -> ForecastGenerationRequestRepository:
    db = Path(td) / "req.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return ForecastGenerationRequestRepository(db_path=str(db))


def test_create_and_get_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        rid = repo.create(
            project_key="tropical",
            generation_mode="db_config",
            request_status="running",
            validation_status="valid",
            generator_kind="comprehensive",
            forecast_start_date="2026-06-01",
            forecast_cutoff_date="2026-06-24",
            forecast_cutoff_date_basis="operator_supplied",
            requested_by_role="operator",
            readiness_status_at_request="ready",
            readiness_reasons=[],
        )
        row = repo.get(rid)
        assert row is not None
        assert row["project_key"] == "tropical"
        assert row["generation_mode"] == "db_config"
        assert row["generator_kind"] == "comprehensive"
        assert row["forecast_cutoff_date_basis"] == "operator_supplied"
        assert row["request_status"] == "running"
        assert row["started_utc"] is not None
        assert json.loads(row["readiness_reasons_json"]) == []


def test_update_status_attach_run_and_complete() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        rid = repo.create(
            project_key="tropical",
            generation_mode="file_config",
            request_status="running",
            validation_status="valid",
        )
        repo.attach_run(rid, "run123abc")
        repo.update_status(rid, "completed", run_id="run123abc")
        row = repo.get(rid)
        assert row is not None
        assert row["run_id"] == "run123abc"
        assert row["request_status"] == "completed"
        assert row["completed_utc"] is not None


def test_record_validation_rejection() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        rid = repo.record_validation_rejection(
            project_key="ghost",
            generation_mode="db_config",
            validation_errors=["unknown_project_key"],
        )
        row = repo.get(rid)
        assert row is not None
        assert row["request_status"] == "rejected"
        assert row["validation_status"] == "invalid"
        assert json.loads(row["validation_errors_json"]) == ["unknown_project_key"]
        assert row["failed_utc"] is not None


def test_record_failure_sets_code() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        rid = repo.create(
            project_key="tropical",
            generation_mode="db_config",
            request_status="running",
            validation_status="valid",
        )
        repo.record_failure(rid, "generation_disabled", request_status="rejected")
        row = repo.get(rid)
        assert row is not None
        assert row["request_status"] == "rejected"
        assert row["failure_code"] == "generation_disabled"


def test_list_recent_filters_by_project_and_clamps_limit() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        for _ in range(3):
            repo.create(
                project_key="tropical",
                generation_mode="db_config",
                request_status="completed",
                validation_status="valid",
            )
        repo.create(
            project_key="harbor",
            generation_mode="db_config",
            request_status="completed",
            validation_status="valid",
        )
        assert len(repo.list_recent()) == 4
        assert len(repo.list_recent(project_key="tropical")) == 3
        assert all(r["project_key"] == "tropical" for r in repo.list_recent(project_key="tropical"))
        # limit clamps to [1, 100]
        assert len(repo.list_recent(limit=2)) == 2
        assert len(repo.list_recent(limit=1000)) == 4
        assert len(repo.list_recent(limit=0)) == 1
