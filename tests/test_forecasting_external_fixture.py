"""External forecast fixture path using committed CSV sample."""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.forecast_external_ingest import (
    ForecastExternalIngestService,
)
from hb_assistant.construction.analytics.forecast_external_mapping import (
    ForecastExternalMappingService,
)
from hb_assistant.store.migrator import SQLiteMigrator

FIXTURE_CSV = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "forecasting" / "external_forecast_sample.csv"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _baseline_db(path: Path) -> None:
    SQLiteMigrator(db_path=str(path)).apply()
    conn = sqlite3.connect(str(path))
    conn.execute(
        "INSERT INTO forecast_budget_details (project_key,budget_code_key,source_package,raw_json,created_utc) "
        "VALUES (?,?,?,?,?)",
        ("fixtureproj", "01-100", "pkg", json.dumps({"budget_code_key": "01-100"}), "t"),
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def fixture_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    eval_root = tmp_path / "eval"
    eval_root.mkdir()
    data_root = tmp_path / "data"
    data_root.mkdir()
    db = tmp_path / "base.sqlite"
    _baseline_db(db)
    monkeypatch.setenv("HB_FORECAST_EVAL_ROOT", str(eval_root))
    monkeypatch.setenv("HB_FORECAST_DATA_ROOT", str(data_root))
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(db))
    return {"eval_root": eval_root, "db": db}


def test_external_forecast_fixture_ingest_and_mapping(fixture_env: dict[str, Path]) -> None:
    csv_text = FIXTURE_CSV.read_text(encoding="utf-8")
    ingest = ForecastExternalIngestService()
    preview = ingest.preview(
        filename="external_forecast_sample.csv",
        content_b64=_b64(csv_text),
        source_system="manual",
        period="2026-06",
    )
    assert preview["row_count"] >= 3
    assert preview["import_id"]

    mapping = ForecastExternalMappingService()
    proposed = mapping.propose_mapping(import_id=preview["import_id"], project_key="fixtureproj")
    statuses = {m["mapping_status"] for m in proposed.get("rows", [])}
    assert proposed.get("unmapped_count", 0) >= 1 or proposed.get("mapped_count", 0) >= 1
    assert statuses