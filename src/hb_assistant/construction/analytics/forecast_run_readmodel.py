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

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_config_dto import _friendly_utc

_SURFACE = "analytics.forecast_run_readmodel"
_REQUIRED_SCHEMA_VERSION = 66  # v63 (run-output) + v66 (decision-support)
_DEFAULT_PROJECT = "tropical"
_MAX_ROWS = 5000  # defensive cap per child list

# P9: stamp-format leak guard. The P8 narrative free-text embeds run stamps (source_qa →
# ``forecast period <stamp>``, lineage → ``prior_run=<stamp>``); scrub them before surfacing so the
# narrative never trips ``find_redaction_leaks`` (run_stamp = ``\d{8}_\d{6}``).
_STAMP_RE = re.compile(r"\d{8}_\d{6}")

# Per-scope whitelist of P8 narrative payload keys that are safe to surface. Stamp-format fields
# (forecast_period, accuracy_package_stamp, prior_run_id) are dropped by omission; the free-text
# ``narrative`` is always stamp-scrubbed; ``applied_utc`` is surfaced only as a friendly display.
_NARRATIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "project": (
        "estimated_final_cost",
        "forecast_at_completion",
        "cost_to_complete",
        "variance_to_budget",
        "budget_code_count",
        "risk_count",
        "override_count",
        "warning_count",
    ),
    "budget_code": (
        "budget_code_key",
        "recommended_projected_cost",
        "recommended_cost_to_complete",
        "forecast_action",
        "confidence",
        "risk_count",
        "overridden",
    ),
    "human_override": (
        "budget_code_key",
        "assumption_type",
        "column",
        "original",
        "override",
        "delta_amount",
        "source",
    ),
    "source_qa": (
        "budget_code_count",
        "null_projected_cost_count",
        "zero_projected_cost_count",
        "duplicate_budget_code_keys",
    ),
    "lineage": (
        "context_sha256",
        "analysis_sha256",
        "output_sha256",
        "methodology_sha256",
    ),
}


class ForecastRunReadModelError(RuntimeError):
    """Raised when the read-model is unavailable (fail closed) or a record is unknown."""


def _redact_stamps(text: Any) -> Any:
    """Replace stamp-format substrings in free text with ``[redacted]`` (pass non-strings through)."""
    return _STAMP_RE.sub("[redacted]", text) if isinstance(text, str) else text


def _curate_narrative(
    scope: str, narrative_key: str | None, payload: dict[str, Any]
) -> dict[str, Any] | None:
    """Whitelist-project one P8 narrative payload into a redaction-safe display dict.

    Unknown scope → ``None`` (fail-safe: emit nothing rather than dump raw_json). Stamp-format
    structured fields are dropped by omission from the whitelist; ``applied_utc`` is surfaced as a
    friendly display; the free-text ``narrative`` is stamp-scrubbed.
    """
    fields = _NARRATIVE_FIELDS.get(scope)
    if fields is None:
        return None
    out: dict[str, Any] = {"narrative_key": narrative_key}
    for key in fields:
        out[key] = payload.get(key)
    if scope == "human_override":
        out["applied_display"] = _friendly_utc(payload.get("applied_utc"))
    out["narrative"] = _redact_stamps(payload.get("narrative"))
    return out


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
                    "variance_to_prior_forecast": r["variance_to_prior_forecast"],
                    "created_display": _friendly_utc(r["created_utc"]),
                }
                for r in conn.execute(
                    "SELECT output_id, project_key, estimated_final_cost, cost_to_complete, "
                    "variance_to_budget, variance_to_prior_forecast, created_utc "
                    "FROM forecast_outputs WHERE project_key = ? "
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

    def list_projects(self) -> dict[str, Any]:
        """Distinct project keys that have persisted outputs (with output counts). Empty when unpopulated."""
        conn = self._connect()
        try:
            projects = self._rows(
                conn,
                "SELECT project_key, COUNT(*) AS output_count, MAX(created_utc) AS latest_utc "
                "FROM forecast_outputs GROUP BY project_key ORDER BY project_key LIMIT ?",
                (_MAX_ROWS,),
            )
        finally:
            conn.close()
        for p in projects:
            p["latest_display"] = _friendly_utc(p.pop("latest_utc"))
        return {
            "surface": _SURFACE + ".projects",
            "projects": projects,
            "guardrails": _guardrails(),
        }

    def read_output(self, output_id: str) -> dict[str, Any]:
        """Header + per-code/risk/monthly/probability/changes/staffing/commitment-exposure/
        schedule-phasing detail for one output."""
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
            commitment_exposure = self._rows(
                conn,
                "SELECT budget_code_key, committed_amount, exposure_amount "
                "FROM forecast_output_commitment_exposure WHERE output_id = ? "
                "ORDER BY source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
            schedule_phasing = self._rows(
                conn,
                "SELECT budget_code_key, phase, start_month, end_month, amount "
                "FROM forecast_output_schedule_phasing WHERE output_id = ? "
                "ORDER BY source_row_number LIMIT ?",
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
            "commitment_exposure": commitment_exposure,
            "schedule_phasing": schedule_phasing,
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

    def read_narratives(self, output_id: str) -> dict[str, Any]:
        """Curated, redaction-safe per-scope narratives (P8 forecast_output_narratives) for one output.

        Business content lives in each row's ``raw_json``; this parses it and emits only a per-scope
        whitelist (``_curate_narrative``) — never ``raw_json`` verbatim, never stamp-format fields.
        """
        conn = self._connect()
        try:
            orow = conn.execute(
                "SELECT output_id FROM forecast_outputs WHERE output_id = ?", (output_id,)
            ).fetchone()
            if orow is None:
                raise ForecastRunReadModelError(f"unknown output_id: {output_id!r}")
            rows = self._rows(
                conn,
                "SELECT scope, narrative_key, source_row_number, raw_json "
                "FROM forecast_output_narratives WHERE output_id = ? "
                "ORDER BY scope, source_row_number LIMIT ?",
                (output_id, _MAX_ROWS),
            )
        finally:
            conn.close()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            try:
                payload = json.loads(r["raw_json"]) if r["raw_json"] else {}
            except (ValueError, TypeError):
                payload = {}
            curated = _curate_narrative(r["scope"], r["narrative_key"], payload)
            if curated is not None:
                grouped.setdefault(r["scope"], []).append(curated)
        return {
            "surface": _SURFACE + ".narratives",
            "output_id": output_id,
            "narratives": grouped,
            "guardrails": _guardrails(),
        }
