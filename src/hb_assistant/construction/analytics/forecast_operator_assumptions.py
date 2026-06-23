"""Interactive write+read service for operator-supplied forecast assumptions (v66).

This is the first *interactive* write surface on the managed forecast DB. It persists
operator-entered assumptions directly into the two v66 schema tables —
``forecast_operator_assumptions`` (operator create + edit) and
``forecast_required_assumptions`` (operator create + mark-satisfied). These tables are
deliberately OUTSIDE the gated run-output projection's table set, so the Phase-3 live write
never clobbers them.

Why a direct managed-DB write (not the gated temp-swap-certify projection): operator input
cannot be re-derived, so the certify-by-re-derivation model used for *projected* data does not
apply. This mirrors the app's existing operator-write pattern (``ProjectKeywordsService`` /
``add_project_keyword``): a role-guarded route → service → upsert into ``PathPolicy().get_db_path()``.

Project-scoped: these are project-level operator inputs that feed a forecast, so ``run_id`` is
always NULL. Required-assumption idempotency is keyed on a deterministic PRIMARY-KEY hash of
``project_key:assumption_type`` (``ON CONFLICT(id)``) — NOT the table's
``UNIQUE(run_id, assumption_type)``, which does not dedupe when ``run_id`` is NULL (SQLite treats
NULLs as distinct).

Redaction: read paths SELECT a business-safe column whitelist (never ``raw_json``, never
``run_id``) and render timestamps via ``_friendly_utc``. ``forecast_dto.find_redaction_leaks`` is
the backstop (tests assert every payload is leak-free). Reads open ``mode=ro``; writes open a
mutable connection and commit in a single transaction. Fail-closed: missing/unreadable DB or
schema < 66 → ``ForecastOperatorAssumptionsError`` (→ 503).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_config_dto import _friendly_utc
from hb_assistant.normalize.redaction import hash_value

_SURFACE = "analytics.forecast_operator_assumptions"
_REQUIRED_SCHEMA_VERSION = 66  # v66 decision-support family (incl. the two assumption tables)
_MAX_ROWS = 5000  # defensive cap per list
_ALLOWED_CONFIDENCE_IMPACT = frozenset({"raises", "lowers", "neutral"})


class ForecastOperatorAssumptionsError(RuntimeError):
    """Raised when the service is unavailable (fail closed) or a record is unknown."""


def _utc_now() -> str:
    """Seconds-precision ISO-8601 UTC (no microseconds, so ``_friendly_utc`` parses it)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _guardrails() -> dict[str, Any]:
    return {
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
        "raw_content_never_stored": True,
        "direct_managed_db_write": True,
    }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ForecastOperatorAssumptionsService:
    """Create/edit operator assumptions and create/mark-satisfied required assumptions (v66)."""

    def __init__(self, *, db_path: str | None = None) -> None:
        self._db_path = db_path

    # -- connections / fail-closed validation ---------------------------------

    def _resolved_db_path(self) -> str:
        return self._db_path if self._db_path is not None else str(PathPolicy().get_db_path())

    def _path(self) -> Path:
        path = Path(self._resolved_db_path())
        if not path.exists():
            raise ForecastOperatorAssumptionsError("forecast assumptions DB is not available")
        return path

    def _connect_ro(self) -> sqlite3.Connection:
        path = self._path()
        try:
            conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ForecastOperatorAssumptionsError(
                "forecast assumptions DB could not be opened read-only"
            ) from exc
        return self._validated(conn)

    def _connect_rw(self) -> sqlite3.Connection:
        path = self._path()
        try:
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ForecastOperatorAssumptionsError(
                "forecast assumptions DB could not be opened for write"
            ) from exc
        return self._validated(conn)

    def _validated(self, conn: sqlite3.Connection) -> sqlite3.Connection:
        try:
            self._assert_ready(conn)
        except ForecastOperatorAssumptionsError:
            conn.close()
            raise
        return conn

    def _assert_ready(self, conn: sqlite3.Connection) -> None:
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
            version = int(row["v"]) if row and row["v"] is not None else 0
        except sqlite3.Error as exc:
            raise ForecastOperatorAssumptionsError(
                "forecast assumptions DB schema is unreadable"
            ) from exc
        if version < _REQUIRED_SCHEMA_VERSION:
            raise ForecastOperatorAssumptionsError(
                f"forecast assumptions require schema v{_REQUIRED_SCHEMA_VERSION}; DB is at v{version}"
            )

    # -- operator assumptions -------------------------------------------------

    def create_operator_assumption(
        self,
        project_key: str,
        assumption_type: str,
        *,
        value: str | None = None,
        unit: str | None = None,
        budget_code_key: str | None = None,
        source: str | None = None,
        operator: str | None = None,
        confidence_impact: str | None = None,
        is_required: bool = False,
        notes: str | None = None,
    ) -> dict[str, Any]:
        project_key = _clean(project_key) or ""
        assumption_type = _clean(assumption_type) or ""
        if not project_key or not assumption_type:
            return self._rejected("assumption_rejected", "project_key and assumption_type required")
        impact = _clean(confidence_impact)
        if impact is not None and impact not in _ALLOWED_CONFIDENCE_IMPACT:
            return self._rejected("assumption_rejected", "value rejected: confidence_impact")

        assumption_id = uuid.uuid4().hex[:12]
        now = _utc_now()
        fields = {
            "value": _clean(value),
            "unit": _clean(unit),
            "budget_code_key": _clean(budget_code_key),
            "source": _clean(source),
            "operator": _clean(operator),
            "confidence_impact": impact,
            "notes": _clean(notes),
        }
        conn = self._connect_rw()
        try:
            conn.execute(
                "INSERT INTO forecast_operator_assumptions ("
                "assumption_id, run_id, project_key, assumption_type, budget_code_key, value, unit, "
                "source, operator, confidence_impact, is_required, reused_from_prior, overridden, "
                "raw_json, created_utc, updated_utc) "
                "VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)",
                (
                    assumption_id,
                    project_key,
                    assumption_type,
                    fields["budget_code_key"],
                    fields["value"],
                    fields["unit"],
                    fields["source"],
                    fields["operator"],
                    fields["confidence_impact"],
                    int(bool(is_required)),
                    json.dumps(fields, sort_keys=True),
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "kind": "assumption_created",
            "assumption_id": assumption_id,
            "project_key": project_key,
            "assumption_type": assumption_type,
            "guardrails": _guardrails(),
        }

    def edit_operator_assumption(
        self,
        assumption_id: str,
        *,
        value: str | None = None,
        unit: str | None = None,
        source: str | None = None,
        operator: str | None = None,
        confidence_impact: str | None = None,
        is_required: bool | None = None,
        overridden: bool | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        impact = _clean(confidence_impact)
        if impact is not None and impact not in _ALLOWED_CONFIDENCE_IMPACT:
            return self._rejected("assumption_rejected", "value rejected: confidence_impact")
        conn = self._connect_rw()
        try:
            existing = conn.execute(
                "SELECT value, unit, source, operator, confidence_impact, is_required, overridden, "
                "budget_code_key FROM forecast_operator_assumptions WHERE assumption_id = ?",
                (assumption_id,),
            ).fetchone()
            if existing is None:
                return self._rejected(
                    "assumption_not_found", "unknown assumption", assumption_id=assumption_id
                )
            merged = {
                "value": _clean(value) if value is not None else existing["value"],
                "unit": _clean(unit) if unit is not None else existing["unit"],
                "source": _clean(source) if source is not None else existing["source"],
                "operator": _clean(operator) if operator is not None else existing["operator"],
                "confidence_impact": (
                    impact if confidence_impact is not None else existing["confidence_impact"]
                ),
            }
            new_required = (
                int(bool(is_required)) if is_required is not None else int(existing["is_required"])
            )
            new_overridden = (
                int(bool(overridden)) if overridden is not None else int(existing["overridden"])
            )
            raw = {
                **merged,
                "budget_code_key": existing["budget_code_key"],
                "notes": _clean(notes),
            }
            conn.execute(
                "UPDATE forecast_operator_assumptions SET value = ?, unit = ?, source = ?, "
                "operator = ?, confidence_impact = ?, is_required = ?, overridden = ?, "
                "raw_json = ?, updated_utc = ? WHERE assumption_id = ?",
                (
                    merged["value"],
                    merged["unit"],
                    merged["source"],
                    merged["operator"],
                    merged["confidence_impact"],
                    new_required,
                    new_overridden,
                    json.dumps(raw, sort_keys=True),
                    _utc_now(),
                    assumption_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "kind": "assumption_updated",
            "assumption_id": assumption_id,
            "guardrails": _guardrails(),
        }

    def list_operator_assumptions(self, project_key: str) -> dict[str, Any]:
        project_key = _clean(project_key) or ""
        conn = self._connect_ro()
        try:
            rows = conn.execute(
                "SELECT assumption_id, project_key, assumption_type, budget_code_key, value, unit, "
                "source, operator, confidence_impact, is_required, reused_from_prior, overridden, "
                "created_utc, updated_utc FROM forecast_operator_assumptions WHERE project_key = ? "
                "ORDER BY created_utc DESC, assumption_id LIMIT ?",
                (project_key, _MAX_ROWS),
            ).fetchall()
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".operator.list",
            "project_key": project_key,
            "assumptions": [
                {
                    "assumption_id": r["assumption_id"],
                    "project_key": r["project_key"],
                    "assumption_type": r["assumption_type"],
                    "budget_code_key": r["budget_code_key"],
                    "value": r["value"],
                    "unit": r["unit"],
                    "source": r["source"],
                    "operator": r["operator"],
                    "confidence_impact": r["confidence_impact"],
                    "is_required": bool(r["is_required"]),
                    "reused_from_prior": bool(r["reused_from_prior"]),
                    "overridden": bool(r["overridden"]),
                    "created_display": _friendly_utc(r["created_utc"]),
                    "updated_display": _friendly_utc(r["updated_utc"]),
                }
                for r in rows
            ],
            "guardrails": _guardrails(),
        }

    # -- required assumptions -------------------------------------------------

    def create_required_assumption(
        self, project_key: str, assumption_type: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        project_key = _clean(project_key) or ""
        assumption_type = _clean(assumption_type) or ""
        if not project_key or not assumption_type:
            return self._rejected("required_assumption_rejected", "project_key and type required")
        # Deterministic PK-hash → idempotent canonical row per (project, type). The table's
        # UNIQUE(run_id, assumption_type) does NOT dedupe with run_id NULL, so we key on the PK.
        required_id = hash_value(f"{project_key}:{assumption_type}") or ""
        reason_clean = _clean(reason)
        now = _utc_now()
        conn = self._connect_rw()
        try:
            conn.execute(
                "INSERT INTO forecast_required_assumptions ("
                "id, run_id, project_key, assumption_type, reason, satisfied, raw_json, "
                "created_utc, updated_utc) VALUES (?, NULL, ?, ?, ?, 0, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET reason = excluded.reason, "
                "updated_utc = excluded.updated_utc",
                (
                    required_id,
                    project_key,
                    assumption_type,
                    reason_clean,
                    json.dumps({"reason": reason_clean}, sort_keys=True),
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "kind": "required_assumption_created",
            "id": required_id,
            "project_key": project_key,
            "assumption_type": assumption_type,
            "guardrails": _guardrails(),
        }

    def set_required_assumption_satisfied(
        self, required_id: str, *, satisfied: bool = True
    ) -> dict[str, Any]:
        conn = self._connect_rw()
        try:
            existing = conn.execute(
                "SELECT id FROM forecast_required_assumptions WHERE id = ?", (required_id,)
            ).fetchone()
            if existing is None:
                return self._rejected(
                    "required_assumption_not_found", "unknown required assumption", id=required_id
                )
            conn.execute(
                "UPDATE forecast_required_assumptions SET satisfied = ?, updated_utc = ? "
                "WHERE id = ?",
                (int(bool(satisfied)), _utc_now(), required_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "kind": "required_assumption_updated",
            "id": required_id,
            "satisfied": bool(satisfied),
            "guardrails": _guardrails(),
        }

    def list_required_assumptions(self, project_key: str) -> dict[str, Any]:
        project_key = _clean(project_key) or ""
        conn = self._connect_ro()
        try:
            rows = conn.execute(
                "SELECT id, project_key, assumption_type, reason, satisfied, created_utc, "
                "updated_utc FROM forecast_required_assumptions WHERE project_key = ? "
                "ORDER BY satisfied ASC, created_utc DESC, id LIMIT ?",
                (project_key, _MAX_ROWS),
            ).fetchall()
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".required.list",
            "project_key": project_key,
            "required": [
                {
                    "id": r["id"],
                    "project_key": r["project_key"],
                    "assumption_type": r["assumption_type"],
                    "reason": r["reason"],
                    "satisfied": bool(r["satisfied"]),
                    "created_display": _friendly_utc(r["created_utc"]),
                    "updated_display": _friendly_utc(r["updated_utc"]),
                }
                for r in rows
            ],
            "guardrails": _guardrails(),
        }

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _rejected(kind: str, message: str, **extra: Any) -> dict[str, Any]:
        return {
            "ok": False,
            "kind": kind,
            "message": message,
            **extra,
            "guardrails": _guardrails(),
        }
