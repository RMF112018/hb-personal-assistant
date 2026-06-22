"""Read-only DB-backed read-model for forecast run-output (v63) + decision-support (v66).

Surfaces the persisted forecast run graph the gated live write (Phase 3) lands:
``forecast_outputs`` + its child tables, and the v66 decision-support families
(maturity / data-availability / confidence scorecards+factors / method eligibility /
model selection). Strictly read-only: the DB is opened with ``mode=ro`` (also fails closed if
absent), and the service never writes.

Redaction: the navigable key is the hash-based ``output_id`` (e.g. ``fout-<hex>``) — never the
CFR ``run_id`` (which is stamp-format ``YYYYMMDD_HHMMSS`` and would trip the shared leak scan),
and never ``raw_json``/``source_path``. Each method SELECTs a whitelist of business-safe columns
and renders timestamps as friendly dates. ``forecast_dto.find_redaction_leaks`` is the backstop
(tests assert every payload is leak-free).

Fail-closed: missing/unreadable DB or schema < 66 → ``ForecastRunReadModelError`` (→ 503).
Graceful-empty: a migrated-but-unpopulated DB returns empty lists (200), not an error — the
tables stay empty until an operator runs the Phase-3 gated live write.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_config_dto import _friendly_utc

_SURFACE = "analytics.forecast_run_readmodel"
_REQUIRED_SCHEMA_VERSION = 66  # v63 (run-output) + v66 (decision-support)
_DEFAULT_PROJECT = "tropical"
_MAX_ROWS = 5000  # defensive cap per child list


class ForecastRunReadModelError(RuntimeError):
    """Raised when the read-model is unavailable (fail closed) or a record is unknown."""


def _guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "no_db_write": True,
        "db_access": "read_only",
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
    }


class ForecastRunReadModelService:
    """Read-only browser over the v63 run-output + v66 decision-support tables (mode=ro)."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # -- read-only connection / fail-closed validation ------------------------

    def _resolved_db_path(self) -> str:
        return self.db_path if self.db_path is not None else str(PathPolicy().get_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = Path(self._resolved_db_path())
        if not path.exists():
            raise ForecastRunReadModelError("forecast run-output DB is not available")
        try:
            conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ForecastRunReadModelError(
                "forecast run-output DB could not be opened read-only"
            ) from exc
        try:
            self._assert_ready(conn)
        except ForecastRunReadModelError:
            conn.close()
            raise
        return conn

    def _assert_ready(self, conn: sqlite3.Connection) -> None:
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
            version = int(row["v"]) if row and row["v"] is not None else 0
        except sqlite3.Error as exc:
            raise ForecastRunReadModelError("forecast run-output DB schema is unreadable") from exc
        if version < _REQUIRED_SCHEMA_VERSION:
            raise ForecastRunReadModelError(
                f"forecast run-output requires schema v{_REQUIRED_SCHEMA_VERSION}; DB is at v{version}"
            )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _rows(conn: sqlite3.Connection, sql: str, params: tuple) -> list[dict[str, Any]]:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def _output_header(self, conn: sqlite3.Connection, output_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT output_id, project_key, estimated_final_cost, forecast_at_completion, "
            "cost_to_complete, variance_to_budget, variance_to_prior_forecast, created_utc "
            "FROM forecast_outputs WHERE output_id = ?",
            (output_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "output_id": row["output_id"],
            "project_key": row["project_key"],
            "estimated_final_cost": row["estimated_final_cost"],
            "forecast_at_completion": row["forecast_at_completion"],
            "cost_to_complete": row["cost_to_complete"],
            "variance_to_budget": row["variance_to_budget"],
            "variance_to_prior_forecast": row["variance_to_prior_forecast"],
            "created_display": _friendly_utc(row["created_utc"]),
        }

    # -- public API (each returns surface + guardrails) -----------------------

    def list_outputs(self, project_key: str = _DEFAULT_PROJECT) -> dict[str, Any]:
        """List run-output headers for a project (newest first). Empty list when unpopulated."""
        conn = self._connect()
        try:
            outputs = [
                {
                    "output_id": r["output_id"],
                    "project_key": r["project_key"],
                    "estimated_final_cost": r["estimated_final_cost"],
                    "cost_to_complete": r["cost_to_complete"],
                    "variance_to_budget": r["variance_to_budget"],
                    "created_display": _friendly_utc(r["created_utc"]),
                }
                for r in conn.execute(
                    "SELECT output_id, project_key, estimated_final_cost, cost_to_complete, "
                    "variance_to_budget, created_utc FROM forecast_outputs WHERE project_key = ? "
                    "ORDER BY created_utc DESC, output_id LIMIT ?",
                    (project_key, _MAX_ROWS),
                ).fetchall()
            ]
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".outputs",
            "project_key": project_key,
            "outputs": outputs,
            "guardrails": _guardrails(),
        }

    def read_output(self, output_id: str) -> dict[str, Any]:
        """Header + per-code/risk/monthly/probability/changes/staffing detail for one output."""
        conn = self._connect()
        try:
            header = self._output_header(conn, output_id)
            if header is None:
                raise ForecastRunReadModelError(f"unknown output_id: {output_id!r}")
            budget_codes = self._rows(
                conn,
                "SELECT budget_code_key, cost_code, category, forecast_action, "
                "recommended_projected_cost, recommended_cost_to_complete, confidence "
                "FROM forecast_output_budget_codes WHERE output_id = ? "
                "ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
            risks = self._rows(
                conn,
                "SELECT risk_id, severity, budget_code_key, cost_code, category, risk_type "
                "FROM forecast_output_risks WHERE output_id = ? ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
            monthly = self._rows(
                conn,
                "SELECT budget_code_key, month, value, is_actual "
                "FROM forecast_output_monthly WHERE output_id = ? ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
            probability = self._rows(
                conn,
                "SELECT scope, budget_code_key, p10, p50, p90 "
                "FROM forecast_output_probability WHERE output_id = ? "
                "ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
            changes = self._rows(
                conn,
                "SELECT budget_code_key, change_type, delta_amount "
                "FROM forecast_output_changes WHERE output_id = ? ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
            staffing = self._rows(
                conn,
                "SELECT budget_code_key, role, month, headcount, cost_amount "
                "FROM forecast_output_staffing WHERE output_id = ? ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".output",
            **header,
            "budget_codes": budget_codes,
            "risks": risks,
            "monthly": monthly,
            "probability": probability,
            "changes": changes,
            "staffing": staffing,
            "guardrails": _guardrails(),
        }

    def read_decision_support(self, output_id: str) -> dict[str, Any]:
        """Maturity / availability / confidence / method-eligibility for an output's run."""
        conn = self._connect()
        try:
            orow = conn.execute(
                "SELECT run_id FROM forecast_outputs WHERE output_id = ?", (output_id,)
            ).fetchone()
            if orow is None:
                raise ForecastRunReadModelError(f"unknown output_id: {output_id!r}")
            run_id = orow["run_id"]  # internal only — never emitted (stamp-format)
            maturity_row = conn.execute(
                "SELECT maturity_tier, completed_month_count, nonzero_month_count, lifecycle_signal, "
                "basis FROM forecast_project_maturity_snapshots WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            maturity = dict(maturity_row) if maturity_row is not None else None
            availability = self._rows(
                conn,
                "SELECT domain, availability, coverage, freshness, completeness, mapping_quality, "
                "maturity, score, reason FROM forecast_data_availability_profiles WHERE run_id = ? "
                "ORDER BY domain LIMIT ?",
                (run_id, _MAX_ROWS),
            )
            scorecards = self._rows(
                conn,
                "SELECT scorecard_id, scope, scope_key, score, label "
                "FROM forecast_confidence_scorecards WHERE run_id = ? ORDER BY scope, scope_key LIMIT ?",
                (run_id, _MAX_ROWS),
            )
            for sc in scorecards:
                sc["factors"] = self._rows(
                    conn,
                    "SELECT factor_key, direction, magnitude, reason "
                    "FROM forecast_confidence_factors WHERE scorecard_id = ? ORDER BY factor_key LIMIT ?",
                    (sc.pop("scorecard_id"), _MAX_ROWS),
                )
            method_eligibility = self._rows(
                conn,
                "SELECT method, status, weight, reason "
                "FROM forecast_method_eligibility WHERE run_id = ? ORDER BY method LIMIT ?",
                (run_id, _MAX_ROWS),
            )
            model_selection = self._rows(
                conn,
                "SELECT method, contributed, weight, reason "
                "FROM forecast_model_selection_decisions WHERE run_id = ? ORDER BY method LIMIT ?",
                (run_id, _MAX_ROWS),
            )
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".decision_support",
            "output_id": output_id,
            "maturity": maturity,
            "data_availability": availability,
            "confidence_scorecards": scorecards,
            "method_eligibility": method_eligibility,
            "model_selection": model_selection,
            "guardrails": _guardrails(),
        }
