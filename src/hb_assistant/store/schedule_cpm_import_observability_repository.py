"""Repository for durable CPM import observability rows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .connection import open_connection, transaction


def count_canonical_inputs(
    conn: sqlite3.Connection, *, schedule_version_key: str
) -> tuple[int, int]:
    activities = int(
        conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
            (schedule_version_key,),
        ).fetchone()[0]
    )
    relationships = int(
        conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?",
            (schedule_version_key,),
        ).fetchone()[0]
    )
    return activities, relationships


class ScheduleCpmImportObservabilityRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with open_connection(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def upsert(
        self,
        *,
        import_id: str,
        schedule_version_key: str,
        package_id: str | None,
        trigger_source: str,
        canonical_input_activity_count: int,
        canonical_input_relationship_count: int,
        graph_node_count: int | None,
        graph_edge_count: int | None,
        status: str,
        started_at: str,
        finished_at: str,
        duration_ms: int,
        warning_count: int = 0,
        error_count: int = 0,
        failure_code: str | None = None,
        failure_message: str | None = None,
        failed_step: str | None = None,
        cpm_run_id: str | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        row_id = f"cpmobs-{uuid.uuid4().hex[:16]}"
        payload = {
            "cpm_import_observability_id": row_id,
            "import_id": import_id,
            "package_id": package_id,
            "schedule_version_key": schedule_version_key,
            "trigger_source": trigger_source,
            "canonical_input_activity_count": canonical_input_activity_count,
            "canonical_input_relationship_count": canonical_input_relationship_count,
            "graph_node_count": graph_node_count,
            "graph_edge_count": graph_edge_count,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "warning_count": warning_count,
            "error_count": error_count,
            "failure_code": failure_code,
            "failure_message": failure_message,
            "failed_step": failed_step,
            "cpm_run_id": cpm_run_id,
            "diagnostics_json": json.dumps(diagnostics or {}, sort_keys=True, default=str),
            "created_at": now,
            "updated_at": now,
        }
        cols = list(payload.keys())
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                conn.execute(
                    f"""
                    INSERT INTO schedule_cpm_import_observability ({', '.join(cols)})
                    VALUES ({', '.join('?' for _ in cols)})
                    ON CONFLICT(import_id) DO UPDATE SET
                      package_id=excluded.package_id,
                      schedule_version_key=excluded.schedule_version_key,
                      trigger_source=excluded.trigger_source,
                      canonical_input_activity_count=excluded.canonical_input_activity_count,
                      canonical_input_relationship_count=excluded.canonical_input_relationship_count,
                      graph_node_count=excluded.graph_node_count,
                      graph_edge_count=excluded.graph_edge_count,
                      status=excluded.status,
                      started_at=excluded.started_at,
                      finished_at=excluded.finished_at,
                      duration_ms=excluded.duration_ms,
                      warning_count=excluded.warning_count,
                      error_count=excluded.error_count,
                      failure_code=excluded.failure_code,
                      failure_message=excluded.failure_message,
                      failed_step=excluded.failed_step,
                      cpm_run_id=excluded.cpm_run_id,
                      diagnostics_json=excluded.diagnostics_json,
                      updated_at=excluded.updated_at
                    """,
                    tuple(payload[c] for c in cols),
                )
        return self.get_by_import_id(import_id) or payload

    def get_by_import_id(self, import_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_cpm_import_observability WHERE import_id=?",
                (import_id,),
            ).fetchone()
        if row is None:
            return None
        out = dict(row)
        raw = out.get("diagnostics_json")
        if raw:
            try:
                out["diagnostics"] = json.loads(str(raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                out["diagnostics"] = {}
        else:
            out["diagnostics"] = {}
        return out

    def get_latest_for_schedule_version(self, schedule_version_key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT o.* FROM schedule_cpm_import_observability o
                JOIN schedule_file_imports i ON i.import_id = o.import_id
                WHERE o.schedule_version_key=? AND i.import_status='committed'
                ORDER BY o.updated_at DESC
                LIMIT 1
                """,
                (schedule_version_key,),
            ).fetchone()
        if row is None:
            return None
        out = dict(row)
        raw = out.get("diagnostics_json")
        out["diagnostics"] = json.loads(str(raw)) if raw else {}
        return out
