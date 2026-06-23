"""Service-level tests for the operator-assumptions capture write+read surface (v66).

Exercises ForecastOperatorAssumptionsService directly against a migrated temp DB: create/edit/list
operator assumptions, idempotent required-assumption create (working around the ineffective
UNIQUE(run_id, assumption_type) on NULL run_id), satisfied toggle, not-found handling, input
rejection, and the redaction contract (no raw_json/run_id ever surfaced on the read paths).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_operator_assumptions import (
    ForecastOperatorAssumptionsService,
)
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT = "tropical"


def _service(tmp_path: Path) -> ForecastOperatorAssumptionsService:
    db = tmp_path / "assumptions.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    return ForecastOperatorAssumptionsService(db_path=str(db))


def _conn(svc: ForecastOperatorAssumptionsService) -> sqlite3.Connection:
    conn = sqlite3.connect(svc._resolved_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def test_create_operator_assumption_persists_project_scoped_row(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    res = svc.create_operator_assumption(
        PROJECT, "labor_rate", value="125.00", unit="usd_per_hour", confidence_impact="raises"
    )
    assert res["ok"] is True and res["kind"] == "assumption_created"
    aid = res["assumption_id"]

    conn = _conn(svc)
    try:
        row = conn.execute(
            "SELECT run_id, project_key, assumption_type, value, raw_json, created_utc, updated_utc "
            "FROM forecast_operator_assumptions WHERE assumption_id = ?",
            (aid,),
        ).fetchone()
    finally:
        conn.close()
    assert row["run_id"] is None  # project-scoped operator input
    assert row["project_key"] == PROJECT
    assert row["assumption_type"] == "labor_rate"
    assert row["raw_json"] and json.loads(row["raw_json"])["value"] == "125.00"
    assert row["created_utc"] == row["updated_utc"]


def test_create_rejects_empty_type_and_bad_confidence_impact(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    assert svc.create_operator_assumption(PROJECT, "  ")["ok"] is False
    assert svc.create_operator_assumption("  ", "labor_rate")["ok"] is False
    bad = svc.create_operator_assumption(PROJECT, "labor_rate", confidence_impact="sideways")
    assert bad["ok"] is False and "confidence_impact" in bad["message"]


def test_edit_merges_fields_and_bumps_updated_only(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    aid = svc.create_operator_assumption(PROJECT, "labor_rate", value="100.00", unit="usd")[
        "assumption_id"
    ]
    edited = svc.edit_operator_assumption(aid, value="150.00", overridden=True)
    assert edited["ok"] is True and edited["kind"] == "assumption_updated"

    conn = _conn(svc)
    try:
        row = conn.execute(
            "SELECT value, unit, overridden, created_utc, updated_utc "
            "FROM forecast_operator_assumptions WHERE assumption_id = ?",
            (aid,),
        ).fetchone()
    finally:
        conn.close()
    assert row["value"] == "150.00"  # changed
    assert row["unit"] == "usd"  # untouched field preserved
    assert row["overridden"] == 1
    assert row["created_utc"] <= row["updated_utc"]


def test_edit_unknown_assumption_returns_not_found(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    res = svc.edit_operator_assumption("does-not-exist", value="1")
    assert res["ok"] is False and res["kind"] == "assumption_not_found"


def test_required_assumption_create_is_idempotent(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    first = svc.create_required_assumption(PROJECT, "escalation_rate", reason="needed for trades")
    second = svc.create_required_assumption(PROJECT, "escalation_rate", reason="updated reason")
    assert first["id"] == second["id"]  # deterministic PK-hash dedupe

    conn = _conn(svc)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM forecast_required_assumptions WHERE project_key = ? "
            "AND assumption_type = ?",
            (PROJECT, "escalation_rate"),
        ).fetchone()["n"]
    finally:
        conn.close()
    assert count == 1  # NOT two rows despite UNIQUE(run_id, assumption_type) being NULL-ineffective


def test_set_required_satisfied_toggles_and_unknown_not_found(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    rid = svc.create_required_assumption(PROJECT, "escalation_rate")["id"]
    assert svc.set_required_assumption_satisfied(rid, satisfied=True)["satisfied"] is True

    listed = svc.list_required_assumptions(PROJECT)["required"]
    assert listed[0]["satisfied"] is True

    assert svc.set_required_assumption_satisfied("nope")["kind"] == "required_assumption_not_found"


def test_list_paths_are_redaction_safe(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # Inject redaction bait into a stored raw_json + an embedded run-stamp source: the read paths
    # must never surface raw_json/run_id, so the leak scan stays clean.
    svc.create_operator_assumption(
        PROJECT, "labor_rate", value="125.00", source="estimating call 2026-06", notes="ok"
    )
    svc.create_required_assumption(PROJECT, "escalation_rate", reason="trade coverage")

    conn = sqlite3.connect(svc._resolved_db_path())
    try:
        conn.execute(
            "UPDATE forecast_operator_assumptions SET raw_json = ?, run_id = ?",
            ('{"source_path": "/Users/bobby/forecast/20260101_000000/x.jsonl"}', "20260101_000000"),
        )
        conn.commit()
    finally:
        conn.close()

    ops = svc.list_operator_assumptions(PROJECT)
    req = svc.list_required_assumptions(PROJECT)
    assert find_redaction_leaks(ops) == []
    assert find_redaction_leaks(req) == []
    assert "raw_json" not in json.dumps(ops)
    assert "run_id" not in json.dumps(ops)
    assert "20260101_000000" not in json.dumps(ops)
    # friendly display rendered, not a raw stamp
    assert ops["assumptions"][0]["created_display"]
