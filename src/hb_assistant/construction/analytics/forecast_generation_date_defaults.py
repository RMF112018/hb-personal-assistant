"""Schedule-derived forecast date-default resolver (Phase P-D).

Derives ADVISORY default forecast dates for a project from schedule evidence — chiefly the
forecast cut-off date = the latest reliable schedule DATA/STATUS date (never a finish/horizon date).
Read-only; coded, path-free basis + warning codes; invalid date strings are ignored.

Cut-off priority: (1) schedule data/status date — the latest committed schedule import's data date,
resolved via ``schedule_baseline_quality.resolve_status_date`` (procore_ep_schedules.data_date when
present, else the date encoded in schedule_version_key / import metadata); (2) the import's created_at;
(3) the latest actual activity date; (4) none.

Start-date priority: (1) latest prior request's forecast_start_date; (2) earliest actual cost month;
(3) earliest committed schedule activity start; (4) none.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.schedule_baseline_quality import (
    parse_schedule_date,
    resolve_status_date,
)

_SURFACE = "analytics.forecast_generation_date_defaults"
_REQUIRED_SCHEMA_VERSION = 63  # forecast source tables present; schedule tables are <= v63


class ForecastGenerationDateDefaultsError(RuntimeError):
    """Raised when the date-defaults DB is unavailable (fail closed → 503)."""


@dataclass(frozen=True)
class ForecastGenerationDateDefaults:
    project_key: str
    forecast_start_date: str | None = None
    forecast_start_date_basis: str | None = None
    forecast_cutoff_date: str | None = None
    forecast_cutoff_date_basis: str | None = None
    schedule_version_key: str | None = None
    schedule_data_date: str | None = None
    schedule_data_date_basis: str | None = None
    schedule_source_status: str = "missing"
    # Operator month-window defaults (YYYY-MM): actuals span from earliest→latest actual-cost month,
    # forecast from the month after actuals_through through the latest reliable schedule-finish month.
    actuals_start_month: str | None = None
    actuals_through_month: str | None = None
    forecast_start_month: str | None = None
    forecast_end_month: str | None = None
    forecast_end_month_basis: str | None = None
    warnings: list[str] = field(default_factory=list)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _sdd_basis(source: str | None) -> str:
    if source == "ctx.data_date":
        return "procore_ep_schedules.data_date"
    if source == "schedule_version_key":
        return "schedule_version_key"
    return "schedule_import_metadata"


def _latest_committed_import(conn: sqlite3.Connection, project_key: str) -> dict | None:
    if not _table_exists(conn, "schedule_file_imports"):
        return None
    row = conn.execute(
        "SELECT * FROM schedule_file_imports WHERE project_key=? AND import_status='committed' "
        "ORDER BY created_at DESC, import_id DESC LIMIT 1",
        (project_key,),
    ).fetchone()
    return dict(row) if row is not None else None


def _schedule_data_date(conn: sqlite3.Connection, project_key: str, schedule_id: str | None) -> str | None:
    """procore_ep_schedules.data_date for the project's schedule (guarded; table is runtime-synthetic)."""
    if not schedule_id or not _table_exists(conn, "procore_ep_schedules"):
        return None
    row = conn.execute(
        "SELECT data_date FROM procore_ep_schedules WHERE project_key=? AND schedule_id=? "
        "ORDER BY is_current DESC, updated_utc DESC LIMIT 1",
        (project_key, schedule_id),
    ).fetchone()
    return row["data_date"] if row is not None else None


def _max_valid(values: list[object]) -> str | None:
    best = None
    for raw in values:
        parsed = parse_schedule_date(raw)
        if parsed.parsed and parsed.value is not None and (best is None or parsed.value > best):
            best = parsed.value
    return best.isoformat() if best is not None else None


def _min_valid(values: list[object]) -> str | None:
    best = None
    for raw in values:
        parsed = parse_schedule_date(raw)
        if parsed.parsed and parsed.value is not None and (best is None or parsed.value < best):
            best = parsed.value
    return best.isoformat() if best is not None else None


def _activity_dates(conn: sqlite3.Connection, project_key: str, columns: tuple[str, ...]) -> list[object]:
    if not _table_exists(conn, "procore_ep_schedule_activities"):
        return []
    cols = ", ".join(columns)
    rows = conn.execute(
        f"SELECT {cols} FROM procore_ep_schedule_activities WHERE project_key=?",
        (project_key,),
    ).fetchall()
    out: list[object] = []
    for r in rows:
        out.extend(r[c] for c in columns)
    return out


def _actual_month_bounds(conn: sqlite3.Connection, project_key: str) -> tuple[str | None, str | None]:
    """Earliest and latest actual-cost month (YYYY-MM) across the two actual source tables."""
    earliest: str | None = None
    latest: str | None = None
    for table, col in (
        ("forecast_monthly_actuals_by_budget_code", "month"),
        ("forecast_cost_entries", "accounting_month"),
    ):
        if not _table_exists(conn, table):
            continue
        row = conn.execute(
            f"SELECT MIN({col}) AS lo, MAX({col}) AS hi FROM {table} "
            f"WHERE project_key=? AND {col} IS NOT NULL AND {col} <> ''",
            (project_key,),
        ).fetchone()
        lo = str(row["lo"]).strip()[:7] if row and row["lo"] else None
        hi = str(row["hi"]).strip()[:7] if row and row["hi"] else None
        if lo and (earliest is None or lo < earliest):
            earliest = lo
        if hi and (latest is None or hi > latest):
            latest = hi
    return earliest, latest


def _next_month(year_month: str) -> str | None:
    """The YYYY-MM that follows ``year_month`` (None if unparseable)."""
    try:
        year, month = (int(part) for part in year_month.split("-"))
    except ValueError:
        return None
    if month >= 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


def _schedule_finish_month(conn: sqlite3.Connection, project_key: str) -> str | None:
    """Latest reliable schedule-finish month (YYYY-MM) from committed schedule activities, or None.

    Scans the planned/forecast/actual finish columns and takes the latest valid date. Returns None
    (never a fabricated horizon) when no finish date can be resolved — the caller surfaces a warning
    and the UI requires operator confirmation rather than defaulting to an arbitrary horizon.
    """
    finish = _max_valid(
        _activity_dates(
            conn,
            project_key,
            ("planned_finish", "finish_date", "early_finish", "late_finish", "actual_finish"),
        )
    )
    return finish[:7] if finish else None


def _resolve_start_date(conn: sqlite3.Connection, project_key: str) -> tuple[str | None, str | None, list[str]]:
    warnings: list[str] = []
    # P1: latest prior request's forecast_start_date.
    if _table_exists(conn, "forecast_generation_requests"):
        row = conn.execute(
            "SELECT forecast_start_date FROM forecast_generation_requests "
            "WHERE project_key=? AND forecast_start_date IS NOT NULL "
            "ORDER BY created_utc DESC, request_id DESC LIMIT 1",
            (project_key,),
        ).fetchone()
        if row and parse_schedule_date(row["forecast_start_date"]).parsed:
            return row["forecast_start_date"], "prior_generation_request", warnings
    # P2: earliest actual cost month (YYYY-MM -> YYYY-MM-01).
    for table, col in (
        ("forecast_monthly_actuals_by_budget_code", "month"),
        ("forecast_cost_entries", "accounting_month"),
    ):
        if not _table_exists(conn, table):
            continue
        row = conn.execute(
            f"SELECT MIN({col}) AS m FROM {table} WHERE project_key=? AND {col} IS NOT NULL",
            (project_key,),
        ).fetchone()
        month = row["m"] if row else None
        if month:
            iso = f"{str(month).strip()}-01"
            if parse_schedule_date(iso).parsed:
                return iso, "earliest_actual_cost_month", warnings
    # P3: earliest committed schedule activity start.
    start = _min_valid(_activity_dates(conn, project_key, ("actual_start", "start_date", "planned_start")))
    if start:
        return start, "earliest_schedule_start", warnings
    warnings.append("no_forecast_start_default_available")
    return None, None, warnings


def resolve_forecast_generation_date_defaults(
    conn: sqlite3.Connection, project_key: str
) -> ForecastGenerationDateDefaults:
    """Resolve advisory forecast date defaults for ``project_key`` (read-only)."""
    conn.row_factory = sqlite3.Row
    warnings: list[str] = []

    latest = _latest_committed_import(conn, project_key)
    schedule_version_key = latest.get("schedule_version_key") if latest else None
    if latest is None:
        warnings.append("project_has_no_schedule_versions")

    cutoff_date: str | None = None
    cutoff_basis: str | None = None
    schedule_data_date: str | None = None
    schedule_data_date_basis: str | None = None
    source_status = "missing"

    if latest is not None:
        parts = str(schedule_version_key or "").split("|")
        schedule_id = parts[1] if len(parts) >= 3 else None
        status = resolve_status_date(
            ctx_data_date=_schedule_data_date(conn, project_key, schedule_id),
            import_meta=latest,
            schedule_version_key=schedule_version_key,
        )
        if status.get("invalid_status_date_candidates"):
            warnings.append("invalid_schedule_dates_ignored")
        if status.get("status_date_parse_success") and status.get("status_date"):
            # P1 — schedule data/status date.
            cutoff_date = status["status_date"]
            cutoff_basis = "schedule_data_date"
            schedule_data_date = cutoff_date
            schedule_data_date_basis = _sdd_basis(status.get("status_date_source"))
            source_status = "available"
        else:
            # P2 — import metadata date (created_at, then updated_utc).
            import_date = _max_valid([latest.get("created_at"), latest.get("updated_utc")])
            if import_date:
                cutoff_date = import_date
                cutoff_basis = "schedule_import_created_at"
                schedule_data_date_basis = "schedule_file_imports.created_at"
                source_status = "degraded"
                warnings.append("schedule_data_date_missing_using_import_date")

    if cutoff_date is None:
        # P3 — latest actual activity PROGRESS date. Deliberately excludes updated_at (a row-write
        # metadata timestamp ≈ now), which would otherwise dominate the MAX and never reflect schedule
        # status. Only true actual progress fields are used.
        activity_date = _max_valid(
            _activity_dates(conn, project_key, ("actual_finish", "actual_start"))
        )
        if activity_date:
            cutoff_date = activity_date
            cutoff_basis = "latest_actual_activity_date"
            source_status = "degraded"
            warnings.append("schedule_data_date_missing_using_activity_actual_date")

    if cutoff_date is None:
        # P4 — no schedule-derived cut-off available.
        warnings.append("no_schedule_cutoff_default_available")

    start_date, start_basis, start_warnings = _resolve_start_date(conn, project_key)
    warnings.extend(start_warnings)

    # Operator month-window defaults. Actuals span earliest→latest actual-cost month; forecast starts
    # the month after actuals_through. forecast_end_month is the latest reliable schedule-finish month —
    # NEVER a silent actuals_through+12; when no schedule finish is resolvable we leave it None and warn
    # so the UI requires operator confirmation.
    actuals_start_month, actuals_through_month = _actual_month_bounds(conn, project_key)
    if actuals_start_month is None or actuals_through_month is None:
        warnings.append("no_actual_months_for_window_defaults")
    forecast_start_month = (
        _next_month(actuals_through_month) if actuals_through_month is not None else None
    )
    forecast_end_month = _schedule_finish_month(conn, project_key)
    forecast_end_month_basis: str | None = None
    if forecast_end_month is not None:
        forecast_end_month_basis = "latest_schedule_finish_month"
        # A finish that is not strictly after the forecast start is not a usable horizon default.
        if forecast_start_month is not None and forecast_end_month < forecast_start_month:
            forecast_end_month = None
            forecast_end_month_basis = None
            warnings.append("schedule_finish_before_forecast_start_operator_confirmation_required")
    if forecast_end_month is None:
        warnings.append("no_forecast_end_month_default_operator_confirmation_required")

    return ForecastGenerationDateDefaults(
        project_key=project_key,
        forecast_start_date=start_date,
        forecast_start_date_basis=start_basis,
        forecast_cutoff_date=cutoff_date,
        forecast_cutoff_date_basis=cutoff_basis,
        schedule_version_key=schedule_version_key,
        schedule_data_date=schedule_data_date,
        schedule_data_date_basis=schedule_data_date_basis,
        schedule_source_status=source_status,
        actuals_start_month=actuals_start_month,
        actuals_through_month=actuals_through_month,
        forecast_start_month=forecast_start_month,
        forecast_end_month=forecast_end_month,
        forecast_end_month_basis=forecast_end_month_basis,
        warnings=warnings,
    )


class ForecastGenerationDateDefaultsService:
    """Read-only (mode=ro) service that resolves date defaults for a project."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    def _resolved_db_path(self) -> str:
        return self.db_path if self.db_path is not None else str(PathPolicy().get_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = Path(self._resolved_db_path())
        if not path.exists():
            raise ForecastGenerationDateDefaultsError("forecast project DB is not available")
        try:
            conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ForecastGenerationDateDefaultsError(
                "forecast project DB could not be opened read-only"
            ) from exc
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
            version = int(row["v"]) if row and row["v"] is not None else 0
        except sqlite3.Error as exc:
            conn.close()
            raise ForecastGenerationDateDefaultsError(
                "forecast project DB schema is unreadable"
            ) from exc
        if version < _REQUIRED_SCHEMA_VERSION:
            conn.close()
            raise ForecastGenerationDateDefaultsError(
                f"forecast date defaults require schema v{_REQUIRED_SCHEMA_VERSION}; DB is at v{version}"
            )
        return conn

    def resolve(self, project_key: str) -> ForecastGenerationDateDefaults:
        conn = self._connect()
        try:
            return resolve_forecast_generation_date_defaults(conn, project_key)
        finally:
            conn.close()

    def public(self, project_key: str) -> dict:
        """Redaction-safe response dict for the API route."""
        defaults = self.resolve(project_key)
        return {
            "surface": _SURFACE,
            **asdict(defaults),
            "guardrails": {
                "read_only": True,
                "redaction_safe": True,
                "no_live_endpoint_calls": True,
            },
        }
