"""Read-only generation-project read model (Phase P-B).

Discovers selectable forecast projects from POPULATED DB evidence and reports per-project
availability + a deterministic ``ready``/``degraded``/``blocked`` readiness with coded reasons, so
the Run Center can drive a project selector instead of an output-derived list hard-defaulted to
``tropical``.

Discovery (union of distinct ``project_key``):
  1. ``procore_ep_projects``       — primary project identity (display name / number / procore id).
  2. committed ``schedule_file_imports`` (``import_status='committed'``) — schedule availability.
  3. ``forecast_outputs``          — latest forecast status/history only (NOT authoritative discovery).

Strictly read-only: the DB is opened ``mode=ro`` (fails closed if absent / schema too old). Every
source query is wrapped in a table-existence guard so a Procore-endpoint table that is absent in a
freshly migrated DB degrades to empty rather than raising. Redaction: only coded/business-safe fields
are emitted (no ``source_path``/``raw_json``/``run_id``/stamps); ``find_redaction_leaks`` is the
backstop (tests assert every payload is leak-free). Exact schedule cutoff-date derivation
(``latest_schedule_date``) is deferred to a later phase — emitted as ``None`` here.

Readiness is an EVIDENCE-COMPLETENESS maturity ladder (Phase P-2), not a binary gate:

    no_financial_basis → baseline_only → cost_informed → schedule_informed → full_context

A first forecast is a normal case: a project is ``blocked`` ONLY when it cannot be resolved to an
identity OR has no calculable financial basis at all. A financial basis is the PRESENCE (per
``project_key``) of any of: ``forecast_budget_details`` / ``forecast_cost_entries`` /
``forecast_monthly_actuals_by_budget_code`` (v59 source) OR imported ``forecast_external_forecast_rows``
(v61). Dollar magnitudes live in ``raw_json`` and are NOT parsed here — presence detection only is a
documented v1 limitation. Missing config snapshot, missing schedule, and missing prior forecast are
degraded/informational (confidence-lowering), never blockers. ``forecast_output_commitment_exposure``
is prior-run-derived (``commitment_available``) and never counts as a first-run basis.

Project readiness is evidence-only and INDEPENDENT of the global generation flag: the runtime
``generation_enabled`` toggle is emitted at the top level and gates execution via the global
generation-readiness endpoint + Generate button — it never marks an individual project ``blocked``.

This maturity is intentionally DISTINCT from
``construction.forecast.decision_support_engine._maturity_tier`` (M0–M5), which is a post-generation
LIFECYCLE/time-depth axis (months of actuals); that engine is not reused or modified here.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_config_dto import _friendly_utc
from hb_assistant.construction.analytics.forecast_runtime_config import (
    resolve_db_config_run_enabled,
)

_SURFACE = "analytics.forecast_generation_projects"
# Minimum schema guaranteeing the forecast source tables exist: forecast_outputs (v63); the
# schedule/config/budget tables are v59–v62 (<= 63). Procore-endpoint tables are handled defensively.
_REQUIRED_SCHEMA_VERSION = 63

# Minimum nonzero monthly-actual months below which monthly trend is "sparse" (confidence note).
_SPARSE_MONTHLY_MONTHS = 3

# Evidence-completeness maturity ladder → base confidence band (lifecycle-independent).
_CONFIDENCE_BY_MATURITY = {
    "no_financial_basis": "none",
    "baseline_only": "low",
    "cost_informed": "medium",
    "schedule_informed": "medium",
    "full_context": "high",
}
_CONFIDENCE_ORDER = ("none", "low", "medium", "high")


def _maturity(
    *, has_financial_basis: bool, has_actual_cost: bool, has_schedule: bool, has_prior: bool
) -> str:
    """Evidence-completeness tier (see module docstring). Distinct from decision_support lifecycle."""
    if not has_financial_basis:
        return "no_financial_basis"
    if not has_actual_cost:
        return "baseline_only"
    if not has_schedule:
        return "cost_informed"
    if not has_prior:
        return "schedule_informed"
    return "full_context"


def _confidence(maturity: str, *, has_config: bool) -> str:
    """Confidence from maturity; a missing config snapshot lowers it one tier (floor ``low``)."""
    if maturity == "no_financial_basis":
        return "none"
    base = _CONFIDENCE_BY_MATURITY[maturity]
    if not has_config:  # methodology default in play → lower confidence, never a block
        return _CONFIDENCE_ORDER[max(1, _CONFIDENCE_ORDER.index(base) - 1)]
    return base


def _forecast_basis(
    *, has_monthly: bool, has_cost_entries: bool, has_external: bool, has_budget: bool
) -> str:
    """Coded label for the strongest financial basis present (informational)."""
    if has_monthly:
        return "monthly_actuals"
    if has_cost_entries:
        return "cost_entries"
    if has_external:
        return "external_forecast"
    if has_budget:
        return "budget_details"
    return "none"


class ForecastGenerationProjectReadModelError(RuntimeError):
    """Raised when the generation-project read model DB is unavailable (fail closed → 503)."""


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


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _pick_canonical_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick one procore_ep_projects row per key: prefer is_current=1, then latest updated_utc/key."""
    current_rows = [row for row in rows if int(row.get("is_current") or 0) == 1]
    pool = current_rows or rows
    return max(
        pool,
        key=lambda row: (str(row.get("updated_utc") or ""), str(row.get("record_key") or "")),
    )


class ForecastGenerationProjectReadModelService:
    """Read-only discovery + readiness over the forecast/schedule/procore source tables (mode=ro)."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # -- read-only connection / fail-closed validation ------------------------

    def _resolved_db_path(self) -> str:
        return self.db_path if self.db_path is not None else str(PathPolicy().get_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = Path(self._resolved_db_path())
        if not path.exists():
            raise ForecastGenerationProjectReadModelError("forecast project DB is not available")
        try:
            conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ForecastGenerationProjectReadModelError(
                "forecast project DB could not be opened read-only"
            ) from exc
        try:
            self._assert_ready(conn)
        except ForecastGenerationProjectReadModelError:
            conn.close()
            raise
        return conn

    def _assert_ready(self, conn: sqlite3.Connection) -> None:
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
            version = int(row["v"]) if row and row["v"] is not None else 0
        except sqlite3.Error as exc:
            raise ForecastGenerationProjectReadModelError(
                "forecast project DB schema is unreadable"
            ) from exc
        if version < _REQUIRED_SCHEMA_VERSION:
            raise ForecastGenerationProjectReadModelError(
                f"forecast projects require schema v{_REQUIRED_SCHEMA_VERSION}; DB is at v{version}"
            )

    # -- per-source readers (all defensive: absent table → empty) -------------

    def _identity_rows(self, conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        if not _table_exists(conn, "procore_ep_projects"):
            return {}
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT project_key, record_key, display_name, project_number, project_id, "
                "is_current, updated_utc FROM procore_ep_projects "
                "WHERE project_key IS NOT NULL AND TRIM(project_key) != ''"
            ).fetchall()
        ]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["project_key"]), []).append(row)
        out: dict[str, dict[str, Any]] = {}
        for key, key_rows in grouped.items():
            canonical = _pick_canonical_row(key_rows)
            out[key] = {
                "display_name": canonical.get("display_name"),
                "project_number": canonical.get("project_number"),
                "procore_project_id": canonical.get("project_id"),
            }
        return out

    def _committed_schedule(self, conn: sqlite3.Connection) -> dict[str, str | None]:
        """{project_key: latest committed schedule_version_key} (presence ⇒ committed schedule)."""
        if not _table_exists(conn, "schedule_file_imports"):
            return {}
        out: dict[str, str | None] = {}
        # Ascending so the LATEST committed import wins the version-key assignment per project.
        for r in conn.execute(
            "SELECT project_key, schedule_version_key FROM schedule_file_imports "
            "WHERE import_status='committed' AND project_key IS NOT NULL "
            "ORDER BY created_at ASC, import_id ASC"
        ).fetchall():
            out[str(r["project_key"])] = r["schedule_version_key"]
        return out

    def _activity_keys(self, conn: sqlite3.Connection) -> set[str]:
        if not _table_exists(conn, "procore_ep_schedule_activities"):
            return set()
        return {
            str(r[0])
            for r in conn.execute(
                "SELECT DISTINCT project_key FROM procore_ep_schedule_activities "
                "WHERE project_key IS NOT NULL"
            ).fetchall()
            if r[0]
        }

    def _output_meta(self, conn: sqlite3.Connection) -> dict[str, str | None]:
        if not _table_exists(conn, "forecast_outputs"):
            return {}
        return {
            str(r["project_key"]): r["latest_utc"]
            for r in conn.execute(
                "SELECT project_key, MAX(created_utc) AS latest_utc FROM forecast_outputs "
                "GROUP BY project_key"
            ).fetchall()
        }

    def _config_keys(self, conn: sqlite3.Connection) -> set[str]:
        if not _table_exists(conn, "forecast_config_snapshots"):
            return set()
        return {
            str(r[0])
            for r in conn.execute(
                "SELECT DISTINCT project_key FROM forecast_config_snapshots"
            ).fetchall()
            if r[0]
        }

    def _distinct_project_keys(self, conn: sqlite3.Connection, table: str) -> set[str]:
        """Distinct non-empty project_key in ``table`` (empty if absent). ``table`` is a fixed
        literal allowlist at every call site — safe to interpolate."""
        if not _table_exists(conn, table):
            return set()
        return {
            str(r[0])
            for r in conn.execute(f"SELECT DISTINCT project_key FROM {table}").fetchall()
            if r[0]
        }

    def _monthly_nonzero_counts(self, conn: sqlite3.Connection) -> dict[str, int]:
        """{project_key: distinct months with nonzero actuals}. Nonzero ⇒ real cost incurred
        (zero-amount actual months are tracked but are not an actual-cost signal)."""
        if not _table_exists(conn, "forecast_monthly_actuals_by_budget_code"):
            return {}
        return {
            str(r[0]): int(r[1] or 0)
            for r in conn.execute(
                "SELECT project_key, COUNT(DISTINCT month) FROM "
                "forecast_monthly_actuals_by_budget_code "
                "WHERE project_key IS NOT NULL AND amount IS NOT NULL AND amount != 0 "
                "GROUP BY project_key"
            ).fetchall()
            if r[0]
        }

    # -- public read ----------------------------------------------------------

    def list_generation_projects(self) -> dict[str, Any]:
        """Discover projects across source tables + per-project availability and readiness."""
        generation_enabled = resolve_db_config_run_enabled()
        conn = self._connect()
        try:
            identity = self._identity_rows(conn)
            committed = self._committed_schedule(conn)
            activity_keys = self._activity_keys(conn)
            outputs = self._output_meta(conn)
            config_keys = self._config_keys(conn)
            budget_keys = self._distinct_project_keys(conn, "forecast_budget_details")
            cost_entry_keys = self._distinct_project_keys(conn, "forecast_cost_entries")
            monthly_nonzero = self._monthly_nonzero_counts(conn)
            external_keys = self._distinct_project_keys(conn, "forecast_external_forecast_rows")
            commitment_keys = self._distinct_project_keys(
                conn, "forecast_output_commitment_exposure"
            )
        finally:
            conn.close()

        projects: list[dict[str, Any]] = []
        for key in sorted(set(identity) | set(committed) | set(outputs)):
            meta = identity.get(key, {})
            has_schedule = key in committed or key in activity_keys
            has_activity = key in activity_keys
            has_output = key in outputs
            has_budget = key in budget_keys
            has_cost_entries = key in cost_entry_keys
            nonzero_months = monthly_nonzero.get(key, 0)
            has_monthly = nonzero_months > 0
            has_external = key in external_keys
            has_actual_cost = has_cost_entries or has_monthly
            # Financial basis (first-run safe): any v59 source signal OR an imported baseline.
            # Commitment exposure is prior-run-derived and is NOT a first-run basis.
            has_financial_basis = has_budget or has_cost_entries or has_monthly or has_external
            has_budget_cost = has_budget or has_cost_entries or has_monthly
            has_config = key in config_keys
            has_commitment = key in commitment_keys
            has_identity = key in identity or has_schedule or has_output

            maturity = _maturity(
                has_financial_basis=has_financial_basis,
                has_actual_cost=has_actual_cost,
                has_schedule=has_schedule,
                has_prior=has_output,
            )
            confidence = _confidence(maturity, has_config=has_config)
            basis = _forecast_basis(
                has_monthly=has_monthly,
                has_cost_entries=has_cost_entries,
                has_external=has_external,
                has_budget=has_budget,
            )
            basis_limitations: list[str] = []
            if not has_config:
                basis_limitations.append("no_config_snapshot")
            if not has_actual_cost:
                basis_limitations.append("no_actual_cost")
            if not has_schedule:
                basis_limitations.append("no_schedule_data")
            if not has_output:
                basis_limitations.append("no_prior_forecast")
            if has_monthly and nonzero_months < _SPARSE_MONTHLY_MONTHS:
                basis_limitations.append("sparse_monthly_actuals")

            # Project readiness is evidence-only. The global generation flag (generation_enabled,
            # surfaced at the top level) gates execution elsewhere and never blocks a project here.
            blocking: list[str] = []
            if not has_identity:
                blocking.append("no_project_identity")
            if not has_financial_basis:
                blocking.append("no_financial_basis")
            degraded_factors: list[str] = []
            if not has_config:
                degraded_factors.append("missing_config_snapshot")
            if not has_schedule:
                degraded_factors.append("missing_schedule_data")
            informational: list[str] = []
            if not has_output:
                informational.append("no_prior_forecast_output")

            if blocking:
                status = "blocked"
            elif degraded_factors or maturity in ("baseline_only", "cost_informed"):
                status = "degraded"
            else:
                status = "ready"

            projects.append(
                {
                    "project_key": key,
                    "display_name": meta.get("display_name"),
                    "project_number": meta.get("project_number"),
                    "procore_project_id": meta.get("procore_project_id"),
                    "has_schedule_data": has_schedule,
                    "has_activity_data": has_activity,
                    "latest_schedule_version_key": committed.get(key),
                    "latest_schedule_date": None,  # deferred (procore_ep_schedules not safely joinable)
                    "has_prior_forecast_output": has_output,
                    "latest_forecast_status": "generated" if has_output else None,
                    "latest_forecast_display": _friendly_utc(outputs.get(key)),
                    "has_budget_cost_data": has_budget_cost,
                    "config_snapshot_available": has_config,
                    # Phase P-2 maturity / best-effort metadata (coded, redaction-safe).
                    "forecast_maturity": maturity,
                    "confidence_level": confidence,
                    "forecast_basis": basis,
                    "basis_limitations": basis_limitations,
                    "initial_forecast": not has_output,
                    "prior_forecast_available": has_output,
                    "schedule_available": has_schedule,
                    "actual_cost_available": has_actual_cost,
                    "commitment_available": has_commitment,
                    "readiness_status": status,
                    "readiness_reasons": blocking + degraded_factors + informational,
                }
            )

        return {
            "surface": _SURFACE,
            "generation_enabled": generation_enabled,
            "projects": projects,
            "guardrails": _guardrails(),
        }
