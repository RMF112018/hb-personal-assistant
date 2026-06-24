"""External forecast fixture path using committed CSV sample."""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.forecast_external_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_external_eval_service import (
    ForecastExternalEvalService,
)
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


def test_external_eval_project_eligibility_for_fixtureproj(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hb_assistant.construction.analytics.forecast_external_ingest import ForecastExternalError
    from hb_assistant.forecasting.project_eligibility import (
        assert_eval_project_eligible,
        load_eval_project_allowlist,
    )

    assert_eval_project_eligible("fixtureproj")
    assert_eval_project_eligible("tropical")
    monkeypatch.setenv("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", "fixtureproj,customproj")
    assert "customproj" in load_eval_project_allowlist()
    with pytest.raises(ForecastExternalError, match="not eligible"):
        assert_eval_project_eligible("tropical")


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


def test_external_forecast_xlsx_ingest_parses_sheet(fixture_env: dict[str, Path]) -> None:
    """XLSX upload path: openpyxl-parsed header/rows/sheet names, source stored as .xlsx."""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Forecast"
    ws.append(["Cost Code", "EAC"])
    ws.append(["01-100", 950000])
    ws.append(["02-200", 510000])
    buf = io.BytesIO()
    wb.save(buf)

    ingest = ForecastExternalIngestService()
    preview = ingest.preview(
        filename="external_forecast.xlsx",
        content_b64=base64.b64encode(buf.getvalue()).decode(),
        source_system="excel",
        period="2026-06",
    )
    # xlsx-specific: a real worksheet name is surfaced (CSV yields an empty sheet list).
    assert "Forecast" in preview["sheet_names"]
    assert preview["columns"] == ["Cost Code", "EAC"]
    assert preview["row_count"] == 2
    assert preview["sample_rows"][0]["Cost Code"] == "01-100"
    assert find_redaction_leaks(preview) == []
    # Untrusted source bytes stored immutably as .xlsx under the isolated eval-root.
    import_dir = fixture_env["eval_root"] / "imports" / preview["import_id"]
    assert (import_dir / "source.xlsx").is_file()


def test_external_forecast_fixtureproj_full_evaluate(fixture_env: dict[str, Path]) -> None:
    """Full evaluate() pipeline for a SECOND (non-tropical) project, isolated to the eval-root."""
    csv_text = FIXTURE_CSV.read_text(encoding="utf-8")
    ingest = ForecastExternalIngestService()
    preview = ingest.preview(
        filename="external_forecast_sample.csv",
        content_b64=_b64(csv_text),
        source_system="manual",
        period="2026-06",
    )
    proposed = ForecastExternalMappingService().propose_mapping(
        import_id=preview["import_id"], project_key="fixtureproj"
    )
    res = ForecastExternalEvalService().evaluate(
        preview["import_id"], proposed["proposed_column_roles"], project_key="fixtureproj"
    )
    assert res["status"] == "succeeded"
    assert res["mapped_count"] >= 1  # 01-100 is in the fixtureproj baseline
    assert res["guardrails"]["no_live_db_write"] is True
    assert find_redaction_leaks(res) == []

    eval_dir = fixture_env["eval_root"] / "evaluations" / res["eval_id"]
    # The run is recorded against the SECOND project in the isolated eval record.
    record = json.loads((eval_dir / "eval_record.json").read_text(encoding="utf-8"))
    assert record["project_key"] == "fixtureproj"
    # Per-run eval SQLite + evidence package land ONLY under the isolated eval-root.
    edb = eval_dir / "eval.sqlite"
    assert edb.exists()
    ec = sqlite3.connect(str(edb))
    try:
        assert ec.execute("SELECT COUNT(*) FROM forecast_external_forecasts").fetchone()[0] == 1
    finally:
        ec.close()
    assert len(list(eval_dir.glob("external_forecast_evaluation_package_*"))) == 1
    # The baseline DB stays read-only — its external tables remain empty.
    base = sqlite3.connect(f"file:{fixture_env['db']}?mode=ro", uri=True)
    try:
        assert base.execute("SELECT COUNT(*) FROM forecast_external_forecasts").fetchone()[0] == 0
    finally:
        base.close()