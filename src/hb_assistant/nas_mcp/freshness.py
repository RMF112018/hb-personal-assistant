"""Read-only data-freshness / queue / failure / status reporting for the NAS MCP surface.

Purpose: let a remote client see whether the second-brain data is fresh, stalled, or failing
— so answers don't create false confidence — WITHOUT exposing raw rows, paths, or content.

Design: a fixed set of curated **aggregate-only** queries (``COUNT`` / ``MAX(timestamp)`` /
latest-status-enum) over a hardcoded table set, run over the same read-only
``file:{db}?mode=ro`` + ``PRAGMA query_only`` connection the DB tool uses. Every query is
guarded by a table-existence check so absent data is reported explicitly as
``not_configured`` (vs ``unknown`` for present-but-empty, vs ``ok``/``stale`` for present).
This never widens the generic ``hb_db_select`` allowlist and never returns row content.

The obsidian source-intelligence Python API is NAS-blocked, so all of this reads tables
straight from SQLite; the source watcher is in-memory only and is reported ``unknown`` on NAS.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from .config import NasMcpConfig
from .db_tools import _ro_uri
from .limits import WriteWindowStateError, recent_ai_outputs_write_count, write_window_seconds
from .redaction import redact_text

# Age past which a timestamped domain is flagged stale (present but old). Coarse by design.
DEFAULT_STALE_SECONDS = 90_000  # ~25h

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_UNKNOWN = "unknown"  # configured but no data yet
STATUS_NOT_CONFIGURED = "not_configured"  # table absent
STATUS_FUTURE = "anomaly_future_timestamp"  # last timestamp is in the future — freshness untrustworthy
STATUS_DEGRADED = "degraded_last_run_failed"  # recent timestamp but the latest run's status is a failure
STATUS_BLOCKED = "blocked_or_pending"  # not failing, but blocked/awaiting action (e.g. admin approval)
# Small tolerance for benign clock skew before a future timestamp is treated as an anomaly.
FUTURE_TOLERANCE_SECONDS = 300
# Latest-run status enums that mean the subsystem is failing even if its timestamp looks recent.
_FAILURE_STATUSES = frozenset({"error", "failed", "failure", "fail"})
# Non-failure states that still mean the subsystem is not producing fresh data (surface, don't bury as
# "unknown"): a blocked/pending sync is actionable, not merely "no data yet".
_BLOCKED_STATUSES = frozenset({"pending_admin_approval", "blocked", "disabled", "paused"})


def _apply_last_status(info: dict[str, Any], last_status: Any) -> dict[str, Any]:
    """Attach ``last_status`` and reflect a failing/blocked latest run in the headline.

    The headline ``status`` is derived from timestamp age; a subsystem that ran recently but FAILED
    would otherwise read ``ok`` off a fresh timestamp, and a blocked one (e.g. ``pending_admin_approval``
    with no timestamps) would read a bare ``unknown``. Downgrade ok/stale → degraded on failure, and
    ok/stale/unknown → blocked on a blocked/pending status, so a client sees the actionable state.
    Future/not_configured are left untouched.
    """
    if last_status is not None:
        info["last_status"] = last_status
    normalized = str(last_status).strip().lower()
    if normalized in _FAILURE_STATUSES and info.get("status") in (STATUS_OK, STATUS_STALE):
        info["status"] = STATUS_DEGRADED
    elif normalized in _BLOCKED_STATUSES and info.get("status") in (STATUS_OK, STATUS_STALE, STATUS_UNKNOWN):
        info["status"] = STATUS_BLOCKED
    return info


def _now() -> datetime:
    return datetime.now(UTC)


def _connect(config: NasMcpConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(_ro_uri(str(config.db_path)), uri=True, timeout=5.0)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
    try:
        return conn.execute(sql, params).fetchone()
    except sqlite3.Error:
        return None


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _age_status(ts_value: Any, *, stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict[str, Any]:
    dt = _parse_ts(ts_value)
    if dt is None:
        return {"status": STATUS_UNKNOWN, "last": None, "age_seconds": None}
    age = int((_now() - dt).total_seconds())
    if age < -FUTURE_TOLERANCE_SECONDS:
        # A future-dated timestamp cannot be trusted as "fresh" — surface it as an anomaly (with the
        # real, negative age) instead of silently reporting ok/age 0. Material for scheduling data.
        return {
            "status": STATUS_FUTURE,
            "last": dt.isoformat(),
            "age_seconds": age,
            "note": "last timestamp is in the future; treat freshness as unreliable",
        }
    return {
        "status": STATUS_STALE if age > stale_seconds else STATUS_OK,
        "last": dt.isoformat(),
        "age_seconds": max(age, 0),
    }


# ------------------------------------------------------------------ per-domain readers


def _schema_version(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "schema_migrations"):
        return {"status": STATUS_NOT_CONFIGURED}
    row = _one(conn, "SELECT MAX(version) FROM schema_migrations")
    version = row[0] if row else None
    if version is None:
        return {"status": STATUS_UNKNOWN}
    applied = _one(conn, "SELECT applied_at FROM schema_migrations WHERE version=?", (version,))
    return {"status": STATUS_OK, "version": int(version), "applied_at": applied[0] if applied else None}


def _source_intel(conn: sqlite3.Connection) -> dict[str, Any]:
    has_meta = _table_exists(conn, "source_intelligence_metadata")
    has_events = _table_exists(conn, "source_intelligence_events")
    if not has_meta and not has_events:
        return {"status": STATUS_NOT_CONFIGURED}
    if has_meta:
        last = _one(conn, "SELECT MAX(indexed_at) FROM source_intelligence_metadata")
        info = _age_status(last[0] if last else None)
    else:
        info = {"status": STATUS_UNKNOWN, "last": None, "age_seconds": None}
    if has_events:
        info["error_count"] = _count(conn, "source_intelligence_events", "status='error'")
        info["queued_count"] = _count(conn, "source_intelligence_events", "status='queued'")
    return info


def _daily_brief(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "daily_brief_runs"):
        return {"status": STATUS_NOT_CONFIGURED}
    last = _one(conn, "SELECT MAX(generated_utc) FROM daily_brief_runs")
    info = _age_status(last[0] if last else None)
    latest = _one(
        conn, "SELECT status FROM daily_brief_runs ORDER BY generated_utc DESC LIMIT 1"
    )
    return _apply_last_status(info, latest[0] if latest else None)


def _sync_domain(conn: sqlite3.Connection, table: str, ts_col: str, status_col: str,
                 *, attempted_col: str | None = None) -> dict[str, Any]:
    if not _table_exists(conn, table):
        return {"status": STATUS_NOT_CONFIGURED}
    last = _one(conn, f"SELECT MAX({ts_col}) FROM {table}")  # noqa: S608 (fixed identifiers)
    success_ts = last[0] if last else None
    info = _age_status(success_ts)
    if success_ts is None and attempted_col:
        # No successful sync recorded, but there were attempts — surface the attempt age (stale/ok)
        # instead of a bare "unknown", so a subsystem that keeps running without ever succeeding reads
        # honestly rather than looking simply un-configured.
        att = _one(conn, f"SELECT MAX({attempted_col}) FROM {table}")  # noqa: S608
        attempt_ts = att[0] if att else None
        if attempt_ts is not None:
            info = _age_status(attempt_ts)
            info["never_succeeded"] = True
            info["basis"] = "last_attempt"
    order_col = attempted_col or ts_col
    latest = _one(conn, f"SELECT {status_col} FROM {table} ORDER BY {order_col} DESC LIMIT 1")  # noqa: S608
    return _apply_last_status(info, latest[0] if latest else None)


def _procore(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "procore_live_sync_runs"):
        return {"status": STATUS_NOT_CONFIGURED}
    last = _one(conn, "SELECT MAX(completed_at_utc) FROM procore_live_sync_runs")
    info = _age_status(last[0] if last else None)
    latest = _one(
        conn, "SELECT status FROM procore_live_sync_runs ORDER BY started_at_utc DESC LIMIT 1"
    )
    return _apply_last_status(info, latest[0] if latest else None)


def _count(conn: sqlite3.Connection, table: str, where: str) -> int:
    row = _one(conn, f"SELECT COUNT(*) FROM {table} WHERE {where}")  # noqa: S608 (fixed identifiers)
    return int(row[0]) if row and row[0] is not None else 0


def _ai_outputs_freshness(config: NasMcpConfig) -> dict[str, Any]:
    window = write_window_seconds(config)
    # The freshness *reporter* degrades to unknown if receipt state is unreadable/corrupt;
    # the write *limiter* (broker) fails closed on the same condition — a status read must
    # not itself become a denial.
    try:
        count = recent_ai_outputs_write_count(config, window)
    except WriteWindowStateError:
        return {"status": STATUS_UNKNOWN, "note": "receipt_state_unavailable", "window_seconds": window}
    return {"status": STATUS_OK, "writes_in_window": count, "window_seconds": window}


# ------------------------------------------------------------------- public tools


def data_freshness(config: NasMcpConfig) -> dict[str, Any]:
    """Aggregate freshness across subsystems. Counts/timestamps/enums only; no content."""
    result: dict[str, Any] = {
        "surface": "nas_mcp",
        "generated_at": _now().isoformat(),
        "watcher": {"status": STATUS_UNKNOWN, "note": "not_available_on_nas (in-memory only)"},
        "ai_outputs": _ai_outputs_freshness(config),
    }
    try:
        conn = _connect(config)
    except sqlite3.Error:
        result["db"] = {"status": STATUS_NOT_CONFIGURED, "note": "db_unavailable"}
        return result
    try:
        result["schema_version"] = _schema_version(conn)
        result["source_intelligence"] = _source_intel(conn)
        result["daily_brief"] = _daily_brief(conn)
        result["email_sync"] = _sync_domain(
            conn, "email_sync_state", "last_successful_sync_utc", "sync_status",
            attempted_col="last_attempted_sync_utc")
        result["drive_sync"] = _sync_domain(
            conn, "construction_source_sync_state", "last_successful_sync_utc", "sync_status",
            attempted_col="last_attempted_sync_utc")
        result["calendar_sync"] = _sync_domain(
            conn, "calendar_sync_state", "last_successful_sync_utc", "sync_status",
            attempted_col="last_attempted_sync_utc")
        result["procore_sync"] = _procore(conn)
    finally:
        conn.close()
    return result


def queue_status(config: NasMcpConfig) -> dict[str, Any]:
    """Queue depth / disposition counts for the source-intelligence indexer. No payloads."""
    out: dict[str, Any] = {"surface": "nas_mcp", "generated_at": _now().isoformat()}
    try:
        conn = _connect(config)
    except sqlite3.Error:
        return {**out, "status": STATUS_NOT_CONFIGURED, "note": "db_unavailable"}
    try:
        if not _table_exists(conn, "source_intelligence_events"):
            return {**out, "status": STATUS_NOT_CONFIGURED}
        out["status"] = STATUS_OK
        for disp in ("queued", "processing", "error", "done", "skipped"):
            out[f"{disp}_count"] = _count(conn, "source_intelligence_events", f"status='{disp}'")
        last_event = _one(conn, "SELECT MAX(created_at) FROM source_intelligence_events")
        out["last_event_at"] = last_event[0] if last_event else None
        if _table_exists(conn, "source_intelligence_generated_notes"):
            out["stale_card_count"] = _count(
                conn, "source_intelligence_generated_notes", "generation_status='stale'"
            )
    finally:
        conn.close()
    return out


# Run tables scanned for recent failures: (table, ts_col, error_col).
_FAILURE_TABLES: tuple[tuple[str, str, str], ...] = (
    ("assistant_runs", "started_at", "status"),
    ("second_brain_run_registry", "started_utc", "reason_code"),
    ("construction_source_crawl_runs", "started_at", "error_redacted"),
    ("email_crawl_runs", "started_at", "error_redacted"),
    ("calendar_crawl_runs", "started_at", "error_redacted"),
    ("procore_live_sync_runs", "started_at_utc", "reason_codes_json"),
)


def recent_failures(config: NasMcpConfig, limit: int = 10) -> dict[str, Any]:
    """Recent failure classes + timestamps per subsystem — redacted, counts only, no payloads."""
    out: dict[str, Any] = {"surface": "nas_mcp", "generated_at": _now().isoformat(), "subsystems": {}}
    try:
        conn = _connect(config)
    except sqlite3.Error:
        return {**out, "status": STATUS_NOT_CONFIGURED, "note": "db_unavailable"}
    try:
        for table, ts_col, err_col in _FAILURE_TABLES:
            if not _table_exists(conn, table):
                out["subsystems"][table] = {"status": STATUS_NOT_CONFIGURED}
                continue
            failed = _count(conn, table, "status IN ('error','failed')")
            rows = _rows(
                conn,
                f"SELECT {ts_col}, {err_col} FROM {table} "  # noqa: S608 (fixed identifiers)
                f"WHERE status IN ('error','failed') ORDER BY {ts_col} DESC LIMIT ?",
                (max(1, min(limit, 50)),),
            )
            out["subsystems"][table] = {
                "status": STATUS_OK if failed == 0 else STATUS_STALE,
                "failed_count": failed,
                "recent": [
                    {"at": r[0], "error_class": (redact_text(str(r[1]))[0] if r[1] else None)}
                    for r in rows
                ],
            }
    finally:
        conn.close()
    return out


def last_successful_runs(config: NasMcpConfig) -> dict[str, Any]:
    """Last-success timestamp per subsystem. Timestamps/status only."""
    out: dict[str, Any] = {"surface": "nas_mcp", "generated_at": _now().isoformat(), "subsystems": {}}
    try:
        conn = _connect(config)
    except sqlite3.Error:
        return {**out, "status": STATUS_NOT_CONFIGURED, "note": "db_unavailable"}
    try:
        subs = out["subsystems"]
        if _table_exists(conn, "email_sync_state"):
            r = _one(conn, "SELECT MAX(last_successful_sync_utc) FROM email_sync_state")
            subs["email_sync"] = _age_status(r[0] if r else None)
        if _table_exists(conn, "construction_source_sync_state"):
            r = _one(conn, "SELECT MAX(last_successful_sync_utc) FROM construction_source_sync_state")
            subs["drive_sync"] = _age_status(r[0] if r else None)
        if _table_exists(conn, "procore_live_sync_runs"):
            r = _one(conn, "SELECT MAX(completed_at_utc) FROM procore_live_sync_runs WHERE status='success'")
            subs["procore_sync"] = _age_status(r[0] if r else None)
        if _table_exists(conn, "daily_brief_runs"):
            r = _one(conn, "SELECT MAX(generated_utc) FROM daily_brief_runs")
            subs["daily_brief"] = _age_status(r[0] if r else None)
    finally:
        conn.close()
    return out


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    try:
        return list(conn.execute(sql, params).fetchall())
    except sqlite3.Error:
        return []


def capability_mode(config: NasMcpConfig, override_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Current capability posture — profile, gates, safe mode, active override count."""
    from .profile import gate_status  # noqa: PLC0415 (avoid import cycle at load)

    summary = override_summary or {"active_count": 0}
    return {
        "surface": "nas_mcp",
        "generated_at": _now().isoformat(),
        "exposure_profile": gate_status(getattr(config, "capability_profile", None)),
        "active_override_count": summary.get("active_count", 0),
        "active_overrides": summary.get("active", []),
    }
