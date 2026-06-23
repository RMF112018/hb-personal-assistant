"""DB-backed readers for the v66 operator/required assumption tables (consume-only).

P2: operator assumptions are WRITTEN by the FastAPI Run Center service into the live managed
DB (``construction/analytics/forecast_operator_assumptions.py``); this module READS them
(read-only) so the decision-support engine can apply confidence modifiers + a required-
assumption satisfaction gate. There are deliberately no writers here.

Assumptions are project-scoped: the operator write surface always stores them with
``run_id IS NULL``. Because the table's ``UNIQUE(run_id, assumption_type)`` does not dedupe
NULL run_ids, every read filters explicitly on ``run_id IS NULL`` so only project-level rows
are returned (never any run-scoped rows a future slice might add).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def read_operator_assumptions_from_db(
    conn: sqlite3.Connection, *, project_key: str
) -> list[dict[str, Any]]:
    """Project-scoped operator assumptions (``run_id IS NULL``), oldest first."""
    if not _table_exists(conn, "forecast_operator_assumptions"):
        return []
    rows = conn.execute(
        "SELECT assumption_id, project_key, assumption_type, budget_code_key, value, unit, "
        "source, operator, confidence_impact, is_required, raw_json "
        "FROM forecast_operator_assumptions "
        "WHERE project_key = ? AND run_id IS NULL "
        "ORDER BY created_utc, assumption_id",
        (project_key,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for aid, pk, atype, bck, value, unit, source, operator, impact, is_req, raw in rows:
        out.append(
            {
                "assumption_id": aid,
                "project_key": pk,
                "assumption_type": atype,
                "budget_code_key": bck,
                "value": value,
                "unit": unit,
                "source": source,
                "operator": operator,
                "confidence_impact": impact,
                "is_required": bool(is_req),
                "raw_json": json.loads(raw) if raw else {},
            }
        )
    return out


def read_required_assumptions_from_db(
    conn: sqlite3.Connection, *, project_key: str
) -> list[dict[str, Any]]:
    """Project-scoped required assumptions (``run_id IS NULL``), oldest first."""
    if not _table_exists(conn, "forecast_required_assumptions"):
        return []
    rows = conn.execute(
        "SELECT id, project_key, assumption_type, reason, satisfied, raw_json "
        "FROM forecast_required_assumptions "
        "WHERE project_key = ? AND run_id IS NULL "
        "ORDER BY created_utc, id",
        (project_key,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for rid, pk, atype, reason, satisfied, raw in rows:
        out.append(
            {
                "id": rid,
                "project_key": pk,
                "assumption_type": atype,
                "reason": reason,
                "satisfied": bool(satisfied),
                "raw_json": json.loads(raw) if raw else {},
            }
        )
    return out


def unsatisfied_required_assumptions(
    conn: sqlite3.Connection, *, project_key: str
) -> list[dict[str, Any]]:
    """Required assumptions still unsatisfied (``satisfied = 0``)."""
    return [
        r
        for r in read_required_assumptions_from_db(conn, project_key=project_key)
        if not r["satisfied"]
    ]
