"""Repository for the V83 CPM graph diagnostics tables (additive read/write).

Persists and reads ``schedule_cpm_runs`` and ``schedule_cpm_diagnostics``. Mirrors the
connection/transaction conventions used by ``schedule_activity_repository``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from .connection import open_connection, transaction


def deterministic_cpm_run_id(
    *,
    schedule_version_key: str,
    import_id: str,
    diagnostic_signature: Iterable[str],
    kind: str = "graph",
) -> str:
    """Stable run id derived from version + import + sorted signature (+ run kind).

    Deterministic by construction (no wall-clock / randomness) so rerunning on unchanged
    inputs yields the same ``cpm_run_id`` and stays idempotent. ``kind`` discriminates run
    families (e.g. the forward pass from the graph-only run) and is folded into the hash
    ONLY when it differs from the default ``"graph"`` — so Phase 1 graph-run ids are
    unchanged byte-for-byte.
    """
    signature = "\n".join(sorted(diagnostic_signature))
    payload = f"{schedule_version_key}\x1f{import_id}\x1f{signature}"
    if kind != "graph":
        payload = f"{kind}\x1f{payload}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"cpmrun_{digest}"


class ScheduleCpmDiagnosticsRepository:
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

    def insert_run(
        self, run_row: dict[str, Any], *, conn: Any | None = None
    ) -> str:
        """Insert (or replace) a CPM run summary row; return its cpm_run_id."""
        cols = list(run_row.keys())
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        sql = (
            f"INSERT OR REPLACE INTO schedule_cpm_runs ({names}) VALUES ({placeholders})"
        )
        params = tuple(run_row[c] for c in cols)
        if conn is not None:
            conn.execute(sql, params)
        else:
            with open_connection(self._db_path) as active:
                with transaction(active):
                    active.execute(sql, params)
        return str(run_row["cpm_run_id"])

    def insert_diagnostics(
        self, rows: Iterable[dict[str, Any]], *, conn: Any | None = None
    ) -> int:
        items = list(rows)
        if not items:
            return 0
        cols = list(items[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        sql = f"INSERT INTO schedule_cpm_diagnostics ({names}) VALUES ({placeholders})"
        batch = [tuple(r[c] for c in cols) for r in items]
        if conn is not None:
            conn.executemany(sql, batch)
        else:
            with open_connection(self._db_path) as active:
                with transaction(active):
                    active.executemany(sql, batch)
        return len(items)

    def replace_run_with_diagnostics(
        self, run_row: dict[str, Any], diagnostic_rows: Iterable[dict[str, Any]]
    ) -> str:
        """Persist a run plus its diagnostics in a single transaction (idempotent rerun).

        Any prior diagnostics for the same cpm_run_id are cleared first so a rerun does not
        accumulate duplicate finding rows.
        """
        run_id = str(run_row["cpm_run_id"])
        rows = list(diagnostic_rows)
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    "DELETE FROM schedule_cpm_diagnostics WHERE cpm_run_id=?", (run_id,)
                )
                self.insert_run(run_row, conn=active)
                if rows:
                    self.insert_diagnostics(rows, conn=active)
        return run_id

    def list_runs(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT cpm_run_id, project_key, schedule_version_key, import_id,
                       node_count, edge_count, is_acyclic, diagnostic_count,
                       topological_order_json, analysis_scope, cpm_recalculation_status,
                       calculation_type, schedule_start_anchor, schedule_start_anchor_source,
                       schedule_finish_anchor, schedule_finish_anchor_source,
                       computed_activity_count, blocked_activity_count,
                       source_run_id, total_float_computed_count, free_float_computed_count,
                       path_count, longest_path_activity_count,
                       longest_path_relationship_count, longest_path_duration,
                       longest_path_end_activity_id,
                       critical_float_threshold_days, near_critical_float_threshold_days,
                       computed_critical_activity_count, computed_near_critical_activity_count,
                       computed_noncritical_activity_count, unclassified_activity_count,
                       longest_path_member_count,
                       created_at
                FROM schedule_cpm_runs
                WHERE schedule_version_key=?
                ORDER BY created_at DESC, cpm_run_id
                """,
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_run(self, cpm_run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT cpm_run_id, project_key, schedule_version_key, import_id,
                       node_count, edge_count, is_acyclic, diagnostic_count,
                       topological_order_json, analysis_scope, cpm_recalculation_status,
                       calculation_type, schedule_start_anchor, schedule_start_anchor_source,
                       schedule_finish_anchor, schedule_finish_anchor_source,
                       computed_activity_count, blocked_activity_count,
                       source_run_id, total_float_computed_count, free_float_computed_count,
                       path_count, longest_path_activity_count,
                       longest_path_relationship_count, longest_path_duration,
                       longest_path_end_activity_id,
                       critical_float_threshold_days, near_critical_float_threshold_days,
                       computed_critical_activity_count, computed_near_critical_activity_count,
                       computed_noncritical_activity_count, unclassified_activity_count,
                       longest_path_member_count,
                       created_at
                FROM schedule_cpm_runs
                WHERE cpm_run_id=?
                """,
                (cpm_run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_diagnostics(self, cpm_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT diagnostic_id, cpm_run_id, project_key, schedule_version_key,
                       import_id, activity_id, relationship_ref, diagnostic_type,
                       severity, summary, evidence_json, created_at
                FROM schedule_cpm_diagnostics
                WHERE cpm_run_id=?
                ORDER BY diagnostic_type, activity_id, relationship_ref, diagnostic_id
                """,
                (cpm_run_id,),
            )
            out: list[dict[str, Any]] = []
            for r in cur.fetchall():
                row = dict(r)
                if row.get("evidence_json"):
                    try:
                        row["evidence"] = json.loads(row["evidence_json"])
                    except (TypeError, ValueError):
                        row["evidence"] = None
                else:
                    row["evidence"] = None
                out.append(row)
            return out

    # ------------------------------------------------------------------ V84 forward pass

    def insert_activity_results(
        self, rows: Iterable[dict[str, Any]], *, conn: Any | None = None
    ) -> int:
        return self._insert_rows("schedule_cpm_activity_results", rows, conn=conn)

    def insert_relationship_results(
        self, rows: Iterable[dict[str, Any]], *, conn: Any | None = None
    ) -> int:
        return self._insert_rows("schedule_cpm_relationship_results", rows, conn=conn)

    def _insert_rows(
        self, table: str, rows: Iterable[dict[str, Any]], *, conn: Any | None = None
    ) -> int:
        items = list(rows)
        if not items:
            return 0
        cols = list(items[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        sql = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
        batch = [tuple(r[c] for c in cols) for r in items]
        if conn is not None:
            conn.executemany(sql, batch)
        else:
            with open_connection(self._db_path) as active:
                with transaction(active):
                    active.executemany(sql, batch)
        return len(items)

    def replace_forward_pass_run(
        self,
        run_row: dict[str, Any],
        diagnostic_rows: Iterable[dict[str, Any]],
        activity_rows: Iterable[dict[str, Any]],
        relationship_rows: Iterable[dict[str, Any]],
    ) -> str:
        """Persist a forward-pass run + its diagnostics/activity/relationship results.

        Single transaction; prior rows for the same cpm_run_id are cleared first so a rerun
        replaces rather than accumulates (idempotent).
        """
        run_id = str(run_row["cpm_run_id"])
        diagnostics = list(diagnostic_rows)
        activities = list(activity_rows)
        relationships = list(relationship_rows)
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    "DELETE FROM schedule_cpm_relationship_results WHERE cpm_run_id=?",
                    (run_id,),
                )
                active.execute(
                    "DELETE FROM schedule_cpm_activity_results WHERE cpm_run_id=?", (run_id,)
                )
                active.execute(
                    "DELETE FROM schedule_cpm_diagnostics WHERE cpm_run_id=?", (run_id,)
                )
                self.insert_run(run_row, conn=active)
                if diagnostics:
                    self.insert_diagnostics(diagnostics, conn=active)
                if activities:
                    self.insert_activity_results(activities, conn=active)
                if relationships:
                    self.insert_relationship_results(relationships, conn=active)
        return run_id

    def list_activity_results(self, cpm_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT cpm_run_id, schedule_version_key, project_key, activity_id,
                       activity_name, topological_index, computed_early_start,
                       computed_early_finish, early_start_offset_days, early_finish_offset_days,
                       duration_value, duration_unit, duration_source, predecessor_count,
                       successor_count, forward_pass_status, forward_pass_notes_json,
                       computed_late_start, computed_late_finish, late_start_offset_days,
                       late_finish_offset_days, backward_pass_status, backward_pass_notes_json,
                       terminal_activity_flag, controlling_successor_activity_id,
                       controlling_successor_relationship_id,
                       computed_total_float, computed_total_float_basis,
                       computed_total_float_status, computed_total_float_notes_json,
                       computed_free_float, computed_free_float_basis,
                       computed_free_float_status, computed_free_float_notes_json,
                       controlling_free_float_successor_activity_id,
                       controlling_free_float_relationship_id,
                       computed_critical_flag, computed_near_critical_flag,
                       computed_criticality_class, computed_criticality_status,
                       computed_criticality_basis, computed_criticality_notes_json,
                       critical_float_threshold_days, near_critical_float_threshold_days,
                       longest_path_member_flag, longest_path_sequence,
                       longest_path_membership_basis, longest_path_membership_notes_json,
                       created_at
                FROM schedule_cpm_activity_results
                WHERE cpm_run_id=?
                ORDER BY topological_index, activity_id
                """,
                (cpm_run_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_relationship_results(self, cpm_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT cpm_run_id, schedule_version_key, project_key, relationship_row_id,
                       relationship_ref, predecessor_activity_id, successor_activity_id,
                       relationship_type, lag_value, lag_unit, normalized_lag_days,
                       predecessor_early_start_offset, predecessor_early_finish_offset,
                       candidate_successor_early_start_offset, relationship_calc_status,
                       relationship_calc_notes_json, candidate_predecessor_late_start,
                       candidate_predecessor_late_finish, backward_relationship_calc_status,
                       backward_relationship_calc_notes_json, free_float_candidate,
                       free_float_candidate_status, free_float_candidate_notes_json, created_at
                FROM schedule_cpm_relationship_results
                WHERE cpm_run_id=?
                ORDER BY successor_activity_id, predecessor_activity_id, relationship_ref
                """,
                (cpm_run_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ----------------------------------------------------------------- V85 backward pass

    def _get_latest_run(
        self, schedule_version_key: str, calculation_type: str
    ) -> dict[str, Any] | None:
        """Most-recent run of a given calculation_type for the version."""
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT cpm_run_id, project_key, schedule_version_key, import_id,
                       node_count, edge_count, is_acyclic, diagnostic_count,
                       topological_order_json, analysis_scope, cpm_recalculation_status,
                       calculation_type, schedule_start_anchor, schedule_start_anchor_source,
                       schedule_finish_anchor, schedule_finish_anchor_source,
                       computed_activity_count, blocked_activity_count,
                       source_run_id, total_float_computed_count, free_float_computed_count,
                       path_count, longest_path_activity_count,
                       longest_path_relationship_count, longest_path_duration,
                       longest_path_end_activity_id,
                       critical_float_threshold_days, near_critical_float_threshold_days,
                       computed_critical_activity_count, computed_near_critical_activity_count,
                       computed_noncritical_activity_count, unclassified_activity_count,
                       longest_path_member_count,
                       created_at
                FROM schedule_cpm_runs
                WHERE schedule_version_key=? AND calculation_type=?
                ORDER BY created_at DESC, cpm_run_id
                LIMIT 1
                """,
                (schedule_version_key, calculation_type),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_forward_pass_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        """Most-recent forward-pass run for the version (the backward pass depends on it)."""
        return self._get_latest_run(schedule_version_key, "forward_pass")

    def get_backward_pass_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        """Most-recent backward-pass run for the version (the float pass depends on it)."""
        return self._get_latest_run(schedule_version_key, "backward_pass")

    def get_float_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        """Most-recent float run for the version (the longest path depends on it)."""
        return self._get_latest_run(schedule_version_key, "float")

    def get_longest_path_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        """Most-recent longest-path run (the criticality classification depends on it)."""
        return self._get_latest_run(schedule_version_key, "longest_path")

    def get_criticality_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        """Most-recent criticality run (the DCMA metric integration depends on it)."""
        return self._get_latest_run(schedule_version_key, "criticality")

    def float_risk_counts(
        self, cpm_run_id: str, *, high_total_float_days: float
    ) -> dict[str, int]:
        """Read-only computed-total-float bucket counts for one CPM run.

        A single aggregate query over schedule_cpm_activity_results (no per-activity
        hydration). Buckets count activities by computed_total_float: negative (< 0),
        zero (== 0), and high (>= the supplied high-total-float threshold).
        ``classified_total_float_count`` is the number of activities with a non-NULL
        computed_total_float; activities with a NULL value are excluded from every bucket.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT
                    COALESCE(
                        SUM(CASE WHEN computed_total_float < 0 THEN 1 ELSE 0 END), 0
                    ) AS negative_total_float_count,
                    COALESCE(
                        SUM(CASE WHEN computed_total_float = 0 THEN 1 ELSE 0 END), 0
                    ) AS zero_total_float_count,
                    COALESCE(
                        SUM(CASE WHEN computed_total_float >= ? THEN 1 ELSE 0 END), 0
                    ) AS high_total_float_count,
                    COALESCE(
                        SUM(CASE WHEN computed_total_float IS NOT NULL THEN 1 ELSE 0 END), 0
                    ) AS classified_total_float_count
                FROM schedule_cpm_activity_results
                WHERE cpm_run_id=?
                """,
                (high_total_float_days, cpm_run_id),
            )
            row = cur.fetchone()
            return {
                "negative_total_float_count": int(row["negative_total_float_count"]),
                "zero_total_float_count": int(row["zero_total_float_count"]),
                "high_total_float_count": int(row["high_total_float_count"]),
                "classified_total_float_count": int(row["classified_total_float_count"]),
            }

    def replace_criticality_run(
        self,
        run_row: dict[str, Any],
        diagnostic_rows: Iterable[dict[str, Any]],
        activity_rows: Iterable[dict[str, Any]],
    ) -> str:
        """Persist a criticality run + its diagnostics/activity classification rows.

        Single transaction; prior rows for the same cpm_run_id are cleared first so a rerun
        replaces rather than accumulates (idempotent). Prior CPM runs are a different
        cpm_run_id and are never touched.
        """
        run_id = str(run_row["cpm_run_id"])
        diagnostics = list(diagnostic_rows)
        activities = list(activity_rows)
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    "DELETE FROM schedule_cpm_activity_results WHERE cpm_run_id=?", (run_id,)
                )
                active.execute(
                    "DELETE FROM schedule_cpm_diagnostics WHERE cpm_run_id=?", (run_id,)
                )
                self.insert_run(run_row, conn=active)
                if diagnostics:
                    self.insert_diagnostics(diagnostics, conn=active)
                if activities:
                    self.insert_activity_results(activities, conn=active)
        return run_id

    def replace_float_run(
        self,
        run_row: dict[str, Any],
        diagnostic_rows: Iterable[dict[str, Any]],
        activity_rows: Iterable[dict[str, Any]],
        relationship_rows: Iterable[dict[str, Any]],
    ) -> str:
        """Persist a float run + its diagnostics/activity/relationship results.

        Single transaction; prior rows for the same cpm_run_id are cleared first so a rerun
        replaces rather than accumulates (idempotent). The forward/backward runs are a
        different cpm_run_id and are never touched.
        """
        run_id = str(run_row["cpm_run_id"])
        diagnostics = list(diagnostic_rows)
        activities = list(activity_rows)
        relationships = list(relationship_rows)
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    "DELETE FROM schedule_cpm_relationship_results WHERE cpm_run_id=?",
                    (run_id,),
                )
                active.execute(
                    "DELETE FROM schedule_cpm_activity_results WHERE cpm_run_id=?", (run_id,)
                )
                active.execute(
                    "DELETE FROM schedule_cpm_diagnostics WHERE cpm_run_id=?", (run_id,)
                )
                self.insert_run(run_row, conn=active)
                if diagnostics:
                    self.insert_diagnostics(diagnostics, conn=active)
                if activities:
                    self.insert_activity_results(activities, conn=active)
                if relationships:
                    self.insert_relationship_results(relationships, conn=active)
        return run_id

    # ----------------------------------------------------------------- V87 longest path

    def insert_paths(self, rows: Iterable[dict[str, Any]], *, conn: Any | None = None) -> int:
        return self._insert_rows("schedule_cpm_paths", rows, conn=conn)

    def insert_path_activities(
        self, rows: Iterable[dict[str, Any]], *, conn: Any | None = None
    ) -> int:
        return self._insert_rows("schedule_cpm_path_activities", rows, conn=conn)

    def replace_longest_path_run(
        self,
        run_row: dict[str, Any],
        diagnostic_rows: Iterable[dict[str, Any]],
        path_rows: Iterable[dict[str, Any]],
        path_activity_rows: Iterable[dict[str, Any]],
    ) -> str:
        """Persist a longest-path run + its diagnostics/path/path-activity rows.

        Single transaction; prior rows for the same cpm_run_id are cleared first so a rerun
        replaces rather than accumulates (idempotent). Prior CPM runs are a different
        cpm_run_id and are never touched.
        """
        run_id = str(run_row["cpm_run_id"])
        diagnostics = list(diagnostic_rows)
        paths = list(path_rows)
        path_activities = list(path_activity_rows)
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    "DELETE FROM schedule_cpm_path_activities WHERE cpm_run_id=?", (run_id,)
                )
                active.execute(
                    "DELETE FROM schedule_cpm_paths WHERE cpm_run_id=?", (run_id,)
                )
                active.execute(
                    "DELETE FROM schedule_cpm_diagnostics WHERE cpm_run_id=?", (run_id,)
                )
                self.insert_run(run_row, conn=active)
                if diagnostics:
                    self.insert_diagnostics(diagnostics, conn=active)
                if paths:
                    self.insert_paths(paths, conn=active)
                if path_activities:
                    self.insert_path_activities(path_activities, conn=active)
        return run_id

    def list_paths(self, cpm_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT path_id, cpm_run_id, schedule_version_key, project_key, path_type,
                       path_rank, start_activity_id, end_activity_id, activity_count,
                       relationship_count, path_duration, path_start_offset_days,
                       path_finish_offset_days, path_total_float, path_basis, path_status,
                       path_notes_json, created_at
                FROM schedule_cpm_paths
                WHERE cpm_run_id=?
                ORDER BY path_rank, path_id
                """,
                (cpm_run_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_path_activities(self, path_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT path_id, cpm_run_id, schedule_version_key, project_key, path_type,
                       path_rank, path_sequence, activity_id, activity_name,
                       relationship_from_previous_id, relationship_from_previous_ref,
                       computed_early_start, computed_early_finish, computed_late_start,
                       computed_late_finish, early_start_offset_days, early_finish_offset_days,
                       computed_total_float, computed_free_float, duration_value,
                       topological_index, selection_basis, selection_notes_json, created_at
                FROM schedule_cpm_path_activities
                WHERE path_id=?
                ORDER BY path_sequence
                """,
                (path_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def replace_backward_pass_run(
        self,
        run_row: dict[str, Any],
        diagnostic_rows: Iterable[dict[str, Any]],
        activity_rows: Iterable[dict[str, Any]],
        relationship_rows: Iterable[dict[str, Any]],
    ) -> str:
        """Persist a backward-pass run + its diagnostics/activity/relationship results.

        Single transaction; prior rows for the same cpm_run_id are cleared first so a rerun
        replaces rather than accumulates (idempotent). The forward-pass run's rows are a
        different cpm_run_id and are never touched.
        """
        run_id = str(run_row["cpm_run_id"])
        diagnostics = list(diagnostic_rows)
        activities = list(activity_rows)
        relationships = list(relationship_rows)
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    "DELETE FROM schedule_cpm_relationship_results WHERE cpm_run_id=?",
                    (run_id,),
                )
                active.execute(
                    "DELETE FROM schedule_cpm_activity_results WHERE cpm_run_id=?", (run_id,)
                )
                active.execute(
                    "DELETE FROM schedule_cpm_diagnostics WHERE cpm_run_id=?", (run_id,)
                )
                self.insert_run(run_row, conn=active)
                if diagnostics:
                    self.insert_diagnostics(diagnostics, conn=active)
                if activities:
                    self.insert_activity_results(activities, conn=active)
                if relationships:
                    self.insert_relationship_results(relationships, conn=active)
        return run_id
