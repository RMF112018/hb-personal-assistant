"""Phase 06B freshness / stale-data read model over local SQLite Procore tables.

Deterministic and **read-only**: classifies every registry endpoint for a project as
``current`` / ``stale`` / ``never_synced`` / ``fail_closed`` / ``unknown`` so the user knows
whether data is current enough to trust, and emits a recommended (never executed) sync command
for stale operational endpoints. No live Procore access, no writeback, no raw values, no
determinations.

Freshness source priority (all written only on a successful sync):
``procore_live_sync_watermarks.last_success_at_utc`` → latest successful
``procore_live_sync_runs.completed_at_utc`` → max ``procore_live_records.last_seen_at_utc`` → none.
Held (``live_verified=False``) endpoints are reported ``fail_closed`` and are excluded from the
operational current/stale tally and the stale list.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..procore import endpoints as ep_registry
from .connection import get_connection

_STATUS_CURRENT = "current"
_STATUS_STALE = "stale"
_STATUS_NEVER = "never_synced"
_STATUS_FAIL_CLOSED = "fail_closed"
_STATUS_UNKNOWN = "unknown"
_RECOMMEND_STATUSES = (_STATUS_STALE, _STATUS_NEVER)


def _open(db_path: Optional[Path]) -> sqlite3.Connection:
    return get_connection(db_path)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_days(now: Optional[datetime], then: Optional[datetime]) -> Optional[int]:
    if now is None or then is None:
        return None
    return (now - then).days


def _recommended_sync_command(project_key: str, endpoint_id: str) -> str:
    return (
        f"HB_PROCORE_LIVE=1 hb-assistant procore live sync --project {project_key} "
        f"--endpoint {endpoint_id} --apply --sqlite-only --max-pages 3 --max-items 100 "
        "--confirm-live-get --json"
    )


def build_freshness_report(
    project_key: str,
    *,
    now_utc: str,
    stale_days: int = 7,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the deterministic freshness/stale report (statuses / counts / timestamps only)."""
    conn = _open(db_path)
    now_dt = _parse_iso(now_utc)

    watermarks = {
        r["endpoint_id"]: r["last_success_at_utc"]
        for r in conn.execute(
            "SELECT endpoint_id, last_success_at_utc FROM procore_live_sync_watermarks "
            "WHERE project_key = ?",
            (project_key,),
        ).fetchall()
    }
    runs = {
        r["endpoint_id"]: r["last_completed"]
        for r in conn.execute(
            """
            SELECT endpoint_id, MAX(completed_at_utc) AS last_completed
              FROM procore_live_sync_runs
             WHERE project_key = ? AND state IN ('success', 'partial_success')
               AND completed_at_utc IS NOT NULL
             GROUP BY endpoint_id
            """,
            (project_key,),
        ).fetchall()
    }
    records: Dict[str, Dict[str, Any]] = {
        r["endpoint_id"]: {"last_seen": r["last_seen"], "count": r["n"]}
        for r in conn.execute(
            """
            SELECT endpoint_id, MAX(last_seen_at_utc) AS last_seen, COUNT(*) AS n
              FROM procore_live_records
             WHERE project_key = ?
             GROUP BY endpoint_id
            """,
            (project_key,),
        ).fetchall()
    }

    endpoints: List[Dict[str, Any]] = []
    summary = {s: 0 for s in (_STATUS_CURRENT, _STATUS_STALE, _STATUS_NEVER, _STATUS_FAIL_CLOSED, _STATUS_UNKNOWN)}

    for adapter in sorted(ep_registry.list_all(), key=lambda a: (a.family, a.endpoint_id)):
        eid = adapter.endpoint_id
        rec = records.get(eid, {})
        record_count = int(rec.get("count", 0) or 0)
        row: Dict[str, Any] = {
            "endpoint_id": eid,
            "family": adapter.family,
            "live_verified": adapter.live_verified,
            "record_count": record_count,
        }

        if not adapter.live_verified:
            row.update({"status": _STATUS_FAIL_CLOSED, "last_success_at_utc": None,
                        "age_days": None, "source": "none", "recommended_sync_command": None})
            summary[_STATUS_FAIL_CLOSED] += 1
            endpoints.append(row)
            continue

        # Freshness source priority: watermark -> latest successful run -> record recency.
        freshness_at: Optional[str] = None
        source = "none"
        for candidate, label in (
            (watermarks.get(eid), "watermark"),
            (runs.get(eid), "sync_run"),
            (rec.get("last_seen"), "records"),
        ):
            if candidate is not None and _parse_iso(candidate) is not None:
                freshness_at, source = candidate, label
                break

        has_signal = eid in watermarks or eid in runs or record_count > 0
        if freshness_at is not None:
            age = _age_days(now_dt, _parse_iso(freshness_at))
            status = _STATUS_CURRENT if (age is not None and age <= stale_days) else _STATUS_STALE
        elif not has_signal:
            status = _STATUS_NEVER
        else:
            status = _STATUS_UNKNOWN

        age_days = _age_days(now_dt, _parse_iso(freshness_at)) if freshness_at else None
        row.update({
            "status": status,
            "last_success_at_utc": freshness_at,
            "age_days": age_days,
            "source": source,
            "recommended_sync_command": (
                _recommended_sync_command(project_key, eid) if status in _RECOMMEND_STATUSES else None
            ),
        })
        summary[status] += 1
        endpoints.append(row)

    stale_endpoints = [
        {"endpoint_id": e["endpoint_id"], "family": e["family"], "status": e["status"],
         "age_days": e["age_days"], "recommended_sync_command": e["recommended_sync_command"]}
        for e in endpoints
        if e["status"] in _RECOMMEND_STATUSES  # operational stale + never_synced only
    ]

    operational_total = summary[_STATUS_CURRENT] + summary[_STATUS_STALE] + summary[_STATUS_NEVER] + summary[_STATUS_UNKNOWN]
    return {
        "command": "hb-assistant procore live stale",
        "ok": True,
        "phase": "Phase 06B Prompt 07",
        "project_key": project_key,
        "generated_at": now_utc,
        "stale_threshold_days": stale_days,
        "summary": {**summary, "operational_total": operational_total},
        "endpoints": endpoints,
        "stale_endpoints": stale_endpoints,
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = ["build_freshness_report"]
