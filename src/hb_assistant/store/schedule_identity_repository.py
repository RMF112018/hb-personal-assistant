"""Repository and resolver for canonical schedule identities."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .connection import get_connection, open_connection, transaction


def normalize_schedule_identity_value(value: Any) -> str | None:
    collapsed = re.sub(r"\s+", " ", str(value or "").strip().lower())
    normalized = "".join(ch for ch in collapsed if ch.isalnum())
    return normalized or None


def sanitized_source_filename(value: Any) -> str | None:
    if value is None:
        return None
    base = os.path.basename(str(value).strip())
    if not base:
        return None
    return base.replace("/", "_").replace("\\", "_").replace("..", "_")


def _norm_token(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _norm_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return text or None


def _fingerprint(payload: Any) -> str | None:
    if not payload:
        return None
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def source_system_for_format(source_format: str | None) -> str | None:
    fmt = str(source_format or "").strip().lower()
    if fmt in {"primavera_xer", "primavera_pmxml"}:
        return "primavera"
    if fmt == "ms_project_xml":
        return "microsoft_project"
    if fmt == "procore_json":
        return "procore"
    if fmt == "csv":
        return "csv"
    return fmt or None


@dataclass(frozen=True)
class ScheduleIdentityEvidence:
    project_key: str
    schedule_version_key: str
    import_id: str
    source_system: str | None
    source_format: str | None
    source_filename_redacted: str | None
    normalized_source_project_id: str | None
    normalized_source_project_name: str | None
    canonical_schedule_name: str | None
    activity_id_set_fingerprint: str | None
    wbs_fingerprint: str | None
    relationship_graph_fingerprint: str | None
    activity_ids: frozenset[str]
    activity_count: int
    relationship_count: int
    wbs_count: int


@dataclass(frozen=True)
class ScheduleIdentityResolution:
    identity: dict[str, Any]
    match: dict[str, Any]

    @property
    def schedule_identity_key(self) -> str:
        return str(self.identity["schedule_identity_key"])

    def public_match(self) -> dict[str, Any]:
        return {
            "schedule_identity_key": self.match.get("schedule_identity_key"),
            "schedule_version_key": self.match.get("schedule_version_key"),
            "import_id": self.match.get("import_id"),
            "match_type": self.match.get("match_type"),
            "match_status": self.match.get("match_status"),
            "match_rule": self.match.get("match_rule"),
            "confidence_score": self.match.get("confidence_score"),
            "requires_review": bool(int(self.match.get("requires_review") or 0)),
            "no_match_reason": self.match.get("no_match_reason"),
            "candidate_count": self.match.get("candidate_count"),
            "matched_prior_schedule_version_key": self.match.get(
                "matched_prior_schedule_version_key"
            ),
            "winning_candidate_schedule_version_key": self.match.get(
                "winning_candidate_schedule_version_key"
            ),
        }


class ScheduleIdentityRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def build_evidence(
        *,
        project_key: str,
        schedule_version_key: str,
        import_id: str,
        source_format: str | None,
        source_filename: str | None,
        source_project_id: str | None,
        source_project_name: str | None,
        schedule_name: str | None,
        activities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        wbs_nodes: list[dict[str, Any]],
    ) -> ScheduleIdentityEvidence:
        activity_ids = frozenset(
            _norm_token(a.get("activity_id"))
            for a in activities
            if _norm_token(a.get("activity_id"))
        )
        activity_payload = sorted(activity_ids)
        wbs_payload = sorted(
            (
                {
                    "wbs_id": _norm_token(w.get("wbs_id")),
                    "wbs_code": _norm_text(w.get("wbs_code")),
                    "wbs_name": _norm_text(w.get("wbs_name")),
                    "parent_wbs_id": _norm_token(w.get("parent_wbs_id")),
                    "wbs_path": _norm_text(w.get("wbs_path")),
                }
                for w in wbs_nodes
                if any(
                    w.get(k)
                    for k in (
                        "wbs_id",
                        "wbs_code",
                        "wbs_name",
                        "parent_wbs_id",
                        "wbs_path",
                    )
                )
            ),
            key=lambda row: json.dumps(row, sort_keys=True, default=str),
        )
        rel_payload = sorted(
            (
                {
                    "predecessor_activity_id": _norm_token(r.get("predecessor_activity_id")),
                    "successor_activity_id": _norm_token(r.get("successor_activity_id")),
                    "relationship_type": _norm_token(r.get("relationship_type")),
                    "lag_value": _norm_text(r.get("lag_value")),
                    "lag_unit": _norm_token(r.get("lag_unit")),
                }
                for r in relationships
                if r.get("predecessor_activity_id") and r.get("successor_activity_id")
            ),
            key=lambda row: json.dumps(row, sort_keys=True, default=str),
        )
        return ScheduleIdentityEvidence(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            source_system=source_system_for_format(source_format),
            source_format=source_format,
            source_filename_redacted=sanitized_source_filename(source_filename),
            normalized_source_project_id=normalize_schedule_identity_value(source_project_id),
            normalized_source_project_name=normalize_schedule_identity_value(
                source_project_name or schedule_name
            ),
            canonical_schedule_name=schedule_name or source_project_name,
            activity_id_set_fingerprint=_fingerprint(activity_payload),
            wbs_fingerprint=_fingerprint(wbs_payload),
            relationship_graph_fingerprint=_fingerprint(rel_payload),
            activity_ids=activity_ids,
            activity_count=len(activities),
            relationship_count=len(relationships),
            wbs_count=len(wbs_nodes),
        )

    def resolve_and_persist(
        self,
        evidence: ScheduleIdentityEvidence,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> ScheduleIdentityResolution:
        if conn is not None:
            return self._resolve_and_persist(conn, evidence)
        with open_connection(self._db_path) as active:
            with transaction(active):
                return self._resolve_and_persist(active, evidence)

    def _resolve_and_persist(
        self, conn: sqlite3.Connection, evidence: ScheduleIdentityEvidence
    ) -> ScheduleIdentityResolution:
        candidates = self._candidate_rows(conn, evidence.project_key)
        scored = [self._score_candidate(conn, evidence, candidate) for candidate in candidates]
        eligible = [s for s in scored if s["auto_match"]]
        eligible.sort(
            key=lambda s: (float(s["confidence_score"]), str(s["created_at"] or "")),
            reverse=True,
        )

        if not evidence.activity_id_set_fingerprint:
            decision = {
                "match_type": "new_identity",
                "match_status": "requires_review",
                "match_rule": "missing_content_fingerprint",
                "confidence_score": "0.00",
                "requires_review": 1,
                "no_match_reason": "missing_content_fingerprint",
                "candidate_count": len(candidates),
            }
            identity_key = self._new_identity_key()
        elif not candidates:
            decision = {
                "match_type": "new_identity",
                "match_status": "resolved",
                "match_rule": "first_identity_for_project",
                "confidence_score": "1.00",
                "requires_review": 0,
                "no_match_reason": "no_prior_identity_version",
                "candidate_count": 0,
            }
            identity_key = self._new_identity_key()
        elif len(eligible) == 1:
            winner = eligible[0]
            decision = {
                "match_type": winner["match_type"],
                "match_status": "resolved",
                "match_rule": winner["match_rule"],
                "confidence_score": winner["confidence_score"],
                "requires_review": 0,
                "no_match_reason": None,
                "candidate_count": len(candidates),
                "matched_existing_identity_key": winner["schedule_identity_key"],
                "matched_prior_schedule_version_key": winner["schedule_version_key"],
                "winning_candidate_schedule_version_key": winner["schedule_version_key"],
            }
            identity_key = str(winner["schedule_identity_key"])
        elif len(eligible) > 1:
            decision = {
                "match_type": "new_identity",
                "match_status": "ambiguous",
                "match_rule": "multiple_content_candidates",
                "confidence_score": "0.00",
                "requires_review": 1,
                "no_match_reason": "multiple_identity_candidates",
                "candidate_count": len(candidates),
                "winning_candidate_schedule_version_key": eligible[0]["schedule_version_key"],
            }
            identity_key = self._new_identity_key()
        else:
            decision = {
                "match_type": "new_identity",
                "match_status": "requires_review",
                "match_rule": "no_content_compatible_match",
                "confidence_score": "0.00",
                "requires_review": 1,
                "no_match_reason": "no_content_compatible_match",
                "candidate_count": len(candidates),
            }
            identity_key = self._new_identity_key()

        observed_evidence = self._observed_evidence(evidence, scored)
        identity = self._upsert_identity(conn, identity_key, evidence, observed_evidence)
        match = self._insert_match(conn, identity_key, evidence, decision, observed_evidence)
        return ScheduleIdentityResolution(identity=identity, match=match)

    def get_match_for_version(
        self, schedule_version_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        sql = """
            SELECT * FROM schedule_version_identity_matches
            WHERE schedule_version_key=?
            ORDER BY created_at DESC, match_id DESC LIMIT 1
        """
        if conn is not None:
            row = conn.execute(sql, (schedule_version_key,)).fetchone()
            return dict(row) if row else None
        with self._conn() as active:
            row = active.execute(sql, (schedule_version_key,)).fetchone()
            return dict(row) if row else None

    def get_identity(
        self, schedule_identity_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        sql = "SELECT * FROM schedule_identities WHERE schedule_identity_key=?"
        if conn is not None:
            row = conn.execute(sql, (schedule_identity_key,)).fetchone()
            return dict(row) if row else None
        with self._conn() as active:
            row = active.execute(sql, (schedule_identity_key,)).fetchone()
            return dict(row) if row else None

    def get_identity_for_version(self, schedule_version_key: str) -> dict[str, Any] | None:
        match = self.get_match_for_version(schedule_version_key)
        if not match:
            return None
        return self.get_identity(str(match["schedule_identity_key"]))

    def list_prior_resolved_versions(
        self, *, schedule_identity_key: str, current_schedule_version_key: str
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT m.*, i.created_at AS import_created_at
                FROM schedule_version_identity_matches m
                JOIN schedule_file_imports i ON i.import_id=m.import_id
                WHERE m.schedule_identity_key=?
                  AND m.schedule_version_key<>?
                  AND m.match_status='resolved'
                  AND m.requires_review=0
                  AND i.import_status='committed'
                ORDER BY i.created_at DESC, m.created_at DESC
                """,
                (schedule_identity_key, current_schedule_version_key),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_identities(
        self, *, project_key: str, show_merged: bool = False
    ) -> list[dict[str, Any]]:
        status_clause = "" if show_merged else "AND identity_status='active'"
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT si.*,
                       COUNT(m.match_id) AS version_count,
                       SUM(CASE WHEN m.requires_review=1
                                  OR m.match_status IN ('requires_review', 'ambiguous')
                                THEN 1 ELSE 0 END) AS review_required_count
                FROM schedule_identities si
                LEFT JOIN schedule_version_identity_matches m
                  ON m.schedule_identity_key=si.schedule_identity_key
                WHERE si.project_key=?
                {status_clause}
                GROUP BY si.schedule_identity_key
                ORDER BY si.identity_status ASC, si.updated_at DESC, si.created_at DESC
                """,
                (project_key,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_identity_detail(
        self, *, project_key: str, schedule_identity_key: str, show_merged: bool = True
    ) -> dict[str, Any] | None:
        with self._conn() as conn:
            identity = conn.execute(
                """
                SELECT * FROM schedule_identities
                WHERE project_key=? AND schedule_identity_key=?
                """,
                (project_key, schedule_identity_key),
            ).fetchone()
            if not identity:
                return None
            identity_row = dict(identity)
            if not show_merged and identity_row.get("identity_status") == "merged":
                return None
            version_rows = conn.execute(
                """
                SELECT m.*, i.created_at AS import_created_at,
                       i.import_status, i.source_filename_redacted AS import_filename_redacted,
                       i.activity_count AS import_activity_count,
                       i.relationship_count AS import_relationship_count,
                       i.wbs_count AS import_wbs_count
                FROM schedule_version_identity_matches m
                LEFT JOIN schedule_file_imports i ON i.import_id=m.import_id
                WHERE m.project_key=? AND m.schedule_identity_key=?
                ORDER BY i.created_at DESC, m.created_at DESC
                """,
                (project_key, schedule_identity_key),
            ).fetchall()
            action_rows = conn.execute(
                """
                SELECT * FROM schedule_identity_manual_actions
                WHERE project_key=?
                  AND (source_identity_key=? OR target_identity_key=?)
                ORDER BY created_at DESC, action_id DESC
                """,
                (project_key, schedule_identity_key, schedule_identity_key),
            ).fetchall()
            return {
                "identity": identity_row,
                "versions": [dict(r) for r in version_rows],
                "manual_actions": [dict(r) for r in action_rows],
            }

    def list_review_queue(self, *, project_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT m.*, si.identity_status, si.canonical_schedule_name,
                       i.created_at AS import_created_at,
                       i.import_status,
                       i.source_filename_redacted AS import_filename_redacted
                FROM schedule_version_identity_matches m
                JOIN schedule_identities si ON si.schedule_identity_key=m.schedule_identity_key
                LEFT JOIN schedule_file_imports i ON i.import_id=m.import_id
                WHERE m.project_key=?
                  AND si.identity_status='active'
                  AND (
                    m.requires_review=1
                    OR m.match_status IN ('requires_review', 'ambiguous')
                    OR (
                      m.no_match_reason IS NOT NULL
                      AND m.match_type NOT IN ('manual_reassign', 'manual_split', 'manual_merge')
                      AND m.match_status<>'resolved'
                    )
                  )
                ORDER BY i.created_at DESC, m.created_at DESC
                """,
                (project_key,),
            ).fetchall()
            return [dict(r) for r in rows]

    def reassign_version_identity(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        target_identity_key: str,
        reason: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        detail_key = target_identity_key
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                match = self._require_match(conn, project_key, schedule_version_key)
                target = self._require_identity(conn, project_key, target_identity_key)
                if target.get("identity_status") != "active":
                    self._raise("schedule_identity_not_active", "target identity is not active")
                source_identity_key = str(match["schedule_identity_key"])
                self._insert_manual_action(
                    conn,
                    project_key=project_key,
                    action_type="reassign",
                    schedule_version_key=schedule_version_key,
                    source_identity_key=source_identity_key,
                    target_identity_key=target_identity_key,
                    reason=reason,
                    actor=actor,
                    evidence={"previous_match": self._action_safe_match(match)},
                )
                conn.execute(
                    """
                    UPDATE schedule_version_identity_matches
                    SET schedule_identity_key=?,
                        match_type='manual_reassign',
                        match_status='resolved',
                        match_rule='operator_manual_reassign',
                        requires_review=0,
                        no_match_reason=NULL,
                        matched_existing_identity_key=?,
                        matched_prior_schedule_version_key=NULL,
                        winning_candidate_schedule_version_key=NULL
                    WHERE match_id=?
                    """,
                    (target_identity_key, target_identity_key, match["match_id"]),
                )
                for identity_key in {source_identity_key, target_identity_key}:
                    self._recalculate_identity_metadata(conn, project_key, identity_key)
        return self.get_identity_detail(
            project_key=project_key, schedule_identity_key=detail_key
        ) or {"identity": target}

    def split_version_identity(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        canonical_schedule_name: str | None = None,
        reason: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        new_identity_key: str | None = None
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                match = self._require_match(conn, project_key, schedule_version_key)
                source_identity_key = str(match["schedule_identity_key"])
                new_identity_key = self._new_identity_key()
                conn.execute(
                    """
                    INSERT INTO schedule_identities (
                      schedule_identity_key, project_key, identity_status, canonical_schedule_name,
                      normalized_source_project_id, normalized_source_project_name, source_system,
                      source_format, representative_activity_id_set_fingerprint,
                      representative_wbs_fingerprint, representative_relationship_graph_fingerprint,
                      first_import_id, first_schedule_version_key, latest_import_id,
                      latest_schedule_version_key, evidence_json
                    ) VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_identity_key,
                        project_key,
                        canonical_schedule_name,
                        match.get("normalized_source_project_id"),
                        match.get("normalized_source_project_name"),
                        match.get("source_system"),
                        match.get("source_format"),
                        match.get("activity_id_set_fingerprint"),
                        match.get("wbs_fingerprint"),
                        match.get("relationship_graph_fingerprint"),
                        match.get("import_id"),
                        schedule_version_key,
                        match.get("import_id"),
                        schedule_version_key,
                        json.dumps(
                            {"manual_split_from_identity_key": source_identity_key},
                            sort_keys=True,
                        ),
                    ),
                )
                self._insert_manual_action(
                    conn,
                    project_key=project_key,
                    action_type="split",
                    schedule_version_key=schedule_version_key,
                    source_identity_key=source_identity_key,
                    target_identity_key=new_identity_key,
                    reason=reason,
                    actor=actor,
                    evidence={"previous_match": self._action_safe_match(match)},
                )
                conn.execute(
                    """
                    UPDATE schedule_version_identity_matches
                    SET schedule_identity_key=?,
                        match_type='manual_split',
                        match_status='resolved',
                        match_rule='operator_manual_split',
                        requires_review=0,
                        no_match_reason=NULL,
                        matched_existing_identity_key=NULL,
                        matched_prior_schedule_version_key=NULL,
                        winning_candidate_schedule_version_key=NULL
                    WHERE match_id=?
                    """,
                    (new_identity_key, match["match_id"]),
                )
                for identity_key in {source_identity_key, new_identity_key}:
                    self._recalculate_identity_metadata(conn, project_key, identity_key)
        assert new_identity_key is not None
        return self.get_identity_detail(
            project_key=project_key, schedule_identity_key=new_identity_key
        ) or {"identity": {"schedule_identity_key": new_identity_key}}

    def merge_identities(
        self,
        *,
        project_key: str,
        source_identity_key: str,
        target_identity_key: str,
        reason: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if source_identity_key == target_identity_key:
            self._raise("schedule_identity_merge_same_identity", "source and target differ")
        detail_key = target_identity_key
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                source = self._require_identity(conn, project_key, source_identity_key)
                target = self._require_identity(conn, project_key, target_identity_key)
                if target.get("identity_status") != "active":
                    self._raise("schedule_identity_not_active", "target identity is not active")
                affected = conn.execute(
                    """
                    SELECT * FROM schedule_version_identity_matches
                    WHERE project_key=? AND schedule_identity_key=?
                    ORDER BY created_at ASC, match_id ASC
                    """,
                    (project_key, source_identity_key),
                ).fetchall()
                self._insert_manual_action(
                    conn,
                    project_key=project_key,
                    action_type="merge",
                    schedule_version_key=None,
                    source_identity_key=source_identity_key,
                    target_identity_key=target_identity_key,
                    reason=reason,
                    actor=actor,
                    evidence={
                        "source_identity": self._action_safe_identity(source),
                        "target_identity": self._action_safe_identity(target),
                        "moved_version_count": len(affected),
                    },
                )
                conn.execute(
                    """
                    UPDATE schedule_version_identity_matches
                    SET schedule_identity_key=?,
                        match_type='manual_merge',
                        match_status='resolved',
                        match_rule='operator_manual_merge',
                        requires_review=0,
                        no_match_reason=NULL,
                        matched_existing_identity_key=?
                    WHERE project_key=? AND schedule_identity_key=?
                    """,
                    (target_identity_key, target_identity_key, project_key, source_identity_key),
                )
                conn.execute(
                    """
                    UPDATE schedule_identities
                    SET identity_status='merged',
                        latest_schedule_version_key=NULL,
                        latest_import_id=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE project_key=? AND schedule_identity_key=?
                    """,
                    (project_key, source_identity_key),
                )
                self._recalculate_identity_metadata(conn, project_key, target_identity_key)
        return self.get_identity_detail(
            project_key=project_key, schedule_identity_key=detail_key
        ) or {"identity": target}

    @staticmethod
    def _raise(code: str, message: str) -> None:
        from hb_assistant.construction.analytics.schedule_file_parser import ScheduleImportError

        raise ScheduleImportError(code, message=message)

    @staticmethod
    def _safe_json(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _action_safe_match(match: dict[str, Any]) -> dict[str, Any]:
        return {
            "schedule_identity_key": match.get("schedule_identity_key"),
            "schedule_version_key": match.get("schedule_version_key"),
            "import_id": match.get("import_id"),
            "match_type": match.get("match_type"),
            "match_status": match.get("match_status"),
            "match_rule": match.get("match_rule"),
            "confidence_score": match.get("confidence_score"),
            "requires_review": bool(int(match.get("requires_review") or 0)),
            "no_match_reason": match.get("no_match_reason"),
            "candidate_count": match.get("candidate_count"),
            "source_filename_basename": match.get("source_filename_redacted"),
        }

    @staticmethod
    def _action_safe_identity(identity: dict[str, Any]) -> dict[str, Any]:
        return {
            "schedule_identity_key": identity.get("schedule_identity_key"),
            "project_key": identity.get("project_key"),
            "identity_status": identity.get("identity_status"),
            "canonical_schedule_name": identity.get("canonical_schedule_name"),
            "latest_schedule_version_key": identity.get("latest_schedule_version_key"),
        }

    def _require_match(
        self, conn: sqlite3.Connection, project_key: str, schedule_version_key: str
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT * FROM schedule_version_identity_matches
            WHERE project_key=? AND schedule_version_key=?
            ORDER BY created_at DESC, match_id DESC LIMIT 1
            """,
            (project_key, schedule_version_key),
        ).fetchone()
        if row is None:
            self._raise("schedule_identity_match_not_found", "schedule identity match not found")
        return dict(row)

    def _require_identity(
        self, conn: sqlite3.Connection, project_key: str, schedule_identity_key: str
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT * FROM schedule_identities
            WHERE project_key=? AND schedule_identity_key=?
            """,
            (project_key, schedule_identity_key),
        ).fetchone()
        if row is None:
            self._raise("schedule_identity_not_found", "schedule identity not found")
        return dict(row)

    def _insert_manual_action(
        self,
        conn: sqlite3.Connection,
        *,
        project_key: str,
        action_type: str,
        schedule_version_key: str | None,
        source_identity_key: str | None,
        target_identity_key: str | None,
        reason: str | None,
        actor: str | None,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "action_id": f"sima-{uuid.uuid4().hex}",
            "project_key": project_key,
            "action_type": action_type,
            "schedule_version_key": schedule_version_key,
            "source_identity_key": source_identity_key,
            "target_identity_key": target_identity_key,
            "reason": reason,
            "actor": actor,
            "evidence_json": json.dumps(evidence, sort_keys=True, default=str),
        }
        cols = list(row)
        conn.execute(
            f"INSERT INTO schedule_identity_manual_actions ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            tuple(row[c] for c in cols),
        )
        return row

    @staticmethod
    def _metadata_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
        data_date = parse_schedule_version_data_date(str(row.get("schedule_version_key") or ""))
        if data_date is not None:
            return (1, data_date.isoformat(), str(row.get("import_created_at") or ""))
        return (0, str(row.get("import_created_at") or row.get("created_at") or ""), "")

    def _recalculate_identity_metadata(
        self, conn: sqlite3.Connection, project_key: str, schedule_identity_key: str
    ) -> None:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT m.*, i.created_at AS import_created_at
                FROM schedule_version_identity_matches m
                LEFT JOIN schedule_file_imports i ON i.import_id=m.import_id
                WHERE m.project_key=? AND m.schedule_identity_key=?
                ORDER BY i.created_at ASC, m.created_at ASC
                """,
                (project_key, schedule_identity_key),
            ).fetchall()
        ]
        if not rows:
            conn.execute(
                """
                UPDATE schedule_identities
                SET first_import_id=NULL,
                    first_schedule_version_key=NULL,
                    latest_import_id=NULL,
                    latest_schedule_version_key=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE project_key=? AND schedule_identity_key=?
                """,
                (project_key, schedule_identity_key),
            )
            return
        ordered = sorted(rows, key=self._metadata_sort_key)
        first = ordered[0]
        latest = ordered[-1]
        representative = latest
        conn.execute(
            """
            UPDATE schedule_identities
            SET canonical_schedule_name=COALESCE(canonical_schedule_name, ?),
                normalized_source_project_id=?,
                normalized_source_project_name=?,
                source_system=?,
                source_format=?,
                representative_activity_id_set_fingerprint=?,
                representative_wbs_fingerprint=?,
                representative_relationship_graph_fingerprint=?,
                first_import_id=?,
                first_schedule_version_key=?,
                latest_import_id=?,
                latest_schedule_version_key=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE project_key=? AND schedule_identity_key=?
            """,
            (
                representative.get("normalized_source_project_name"),
                representative.get("normalized_source_project_id"),
                representative.get("normalized_source_project_name"),
                representative.get("source_system"),
                representative.get("source_format"),
                representative.get("activity_id_set_fingerprint"),
                representative.get("wbs_fingerprint"),
                representative.get("relationship_graph_fingerprint"),
                first.get("import_id"),
                first.get("schedule_version_key"),
                latest.get("import_id"),
                latest.get("schedule_version_key"),
                project_key,
                schedule_identity_key,
            ),
        )

    def _candidate_rows(self, conn: sqlite3.Connection, project_key: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT m.*, i.created_at AS import_created_at
            FROM schedule_version_identity_matches m
            JOIN schedule_file_imports i ON i.import_id=m.import_id
            JOIN schedule_identities si ON si.schedule_identity_key=m.schedule_identity_key
            WHERE m.project_key=?
              AND m.match_status='resolved'
              AND m.requires_review=0
              AND si.identity_status='active'
              AND i.import_status='committed'
            ORDER BY i.created_at DESC, m.created_at DESC
            """,
            (project_key,),
        ).fetchall()
        by_identity: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            by_identity.setdefault(str(item["schedule_identity_key"]), item)
        return list(by_identity.values())

    def _score_candidate(
        self,
        conn: sqlite3.Connection,
        evidence: ScheduleIdentityEvidence,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        candidate_ids = self._activity_ids_for_version(conn, str(candidate["schedule_version_key"]))
        overlap = self._activity_overlap(evidence.activity_ids, candidate_ids)
        same_activity_fingerprint = (
            evidence.activity_id_set_fingerprint is not None
            and evidence.activity_id_set_fingerprint == candidate.get("activity_id_set_fingerprint")
        )
        same_wbs = (
            evidence.wbs_fingerprint is not None
            and evidence.wbs_fingerprint == candidate.get("wbs_fingerprint")
        )
        same_relationships = (
            evidence.relationship_graph_fingerprint is not None
            and evidence.relationship_graph_fingerprint
            == candidate.get("relationship_graph_fingerprint")
        )
        same_format = str(evidence.source_format or "") == str(candidate.get("source_format") or "")
        source_id_match = (
            evidence.normalized_source_project_id is not None
            and evidence.normalized_source_project_id
            == candidate.get("normalized_source_project_id")
        )
        name_compatible = self._name_compatible(
            evidence.normalized_source_project_name,
            candidate.get("normalized_source_project_name"),
        )
        cross_format = not same_format
        auto_match = False
        match_type = "no_match"
        match_rule = "content_threshold_not_met"
        confidence = 0.0

        if same_activity_fingerprint:
            auto_match = True
            match_type = "exact_activity_fingerprint"
            match_rule = "exact_activity_fingerprint"
            confidence = (
                1.0
                if (source_id_match or name_compatible or same_wbs or same_relationships)
                else 0.95
            )
        elif cross_format:
            if overlap >= 0.95 and (same_wbs or same_relationships) and name_compatible:
                auto_match = True
                match_type = "cross_format_content_match"
                match_rule = "cross_format_overlap_with_structure_and_name"
                confidence = 0.95
        elif overlap >= 0.80:
            auto_match = True
            match_type = "activity_overlap"
            match_rule = "same_format_activity_overlap"
            confidence = (
                0.90
                if (same_wbs or same_relationships or source_id_match or name_compatible)
                else 0.80
            )

        return {
            **candidate,
            "activity_overlap": round(overlap, 4),
            "same_activity_fingerprint": same_activity_fingerprint,
            "same_wbs_fingerprint": same_wbs,
            "same_relationship_graph_fingerprint": same_relationships,
            "same_source_format": same_format,
            "source_project_id_match": source_id_match,
            "source_project_name_compatible": name_compatible,
            "auto_match": auto_match,
            "match_type": match_type,
            "match_rule": match_rule,
            "confidence_score": f"{confidence:.2f}",
        }

    @staticmethod
    def _activity_ids_for_version(
        conn: sqlite3.Connection, schedule_version_key: str
    ) -> frozenset[str]:
        rows = conn.execute(
            """
            SELECT DISTINCT activity_id FROM procore_ep_schedule_activities
            WHERE schedule_version_key=?
            """,
            (schedule_version_key,),
        ).fetchall()
        return frozenset(_norm_token(r[0]) for r in rows if _norm_token(r[0]))

    @staticmethod
    def _activity_overlap(left: frozenset[str], right: frozenset[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / max(len(left), len(right))

    @staticmethod
    def _name_compatible(left: Any, right: Any) -> bool:
        if not left or not right:
            return False
        return str(left) == str(right)

    @staticmethod
    def _new_identity_key() -> str:
        return f"schedule-ident-{uuid.uuid4().hex}"

    @staticmethod
    def _observed_evidence(
        evidence: ScheduleIdentityEvidence, scored: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "observed": {
                "source_system": evidence.source_system,
                "source_format": evidence.source_format,
                "source_filename_basename": evidence.source_filename_redacted,
                "normalized_source_project_id": evidence.normalized_source_project_id,
                "normalized_source_project_name": evidence.normalized_source_project_name,
                "activity_id_set_fingerprint": evidence.activity_id_set_fingerprint,
                "wbs_fingerprint": evidence.wbs_fingerprint,
                "relationship_graph_fingerprint": evidence.relationship_graph_fingerprint,
                "activity_count": evidence.activity_count,
                "relationship_count": evidence.relationship_count,
                "wbs_count": evidence.wbs_count,
            },
            "candidate_summary": [
                {
                    "schedule_identity_key": s.get("schedule_identity_key"),
                    "schedule_version_key": s.get("schedule_version_key"),
                    "activity_overlap": s.get("activity_overlap"),
                    "same_activity_fingerprint": s.get("same_activity_fingerprint"),
                    "same_wbs_fingerprint": s.get("same_wbs_fingerprint"),
                    "same_relationship_graph_fingerprint": s.get(
                        "same_relationship_graph_fingerprint"
                    ),
                    "same_source_format": s.get("same_source_format"),
                    "source_project_id_match": s.get("source_project_id_match"),
                    "source_project_name_compatible": s.get("source_project_name_compatible"),
                    "auto_match": s.get("auto_match"),
                    "match_rule": s.get("match_rule"),
                }
                for s in scored[:10]
            ],
        }

    def _upsert_identity(
        self,
        conn: sqlite3.Connection,
        identity_key: str,
        evidence: ScheduleIdentityEvidence,
        observed_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        existing = conn.execute(
            "SELECT * FROM schedule_identities WHERE schedule_identity_key=?",
            (identity_key,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE schedule_identities
                SET latest_import_id=?,
                    latest_schedule_version_key=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE schedule_identity_key=?
                """,
                (evidence.import_id, evidence.schedule_version_key, identity_key),
            )
        else:
            conn.execute(
                """
                INSERT INTO schedule_identities (
                  schedule_identity_key, project_key, identity_status, canonical_schedule_name,
                  normalized_source_project_id, normalized_source_project_name, source_system,
                  source_format, representative_activity_id_set_fingerprint,
                  representative_wbs_fingerprint, representative_relationship_graph_fingerprint,
                  first_import_id, first_schedule_version_key, latest_import_id,
                  latest_schedule_version_key, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identity_key,
                    evidence.project_key,
                    "active",
                    evidence.canonical_schedule_name,
                    evidence.normalized_source_project_id,
                    evidence.normalized_source_project_name,
                    evidence.source_system,
                    evidence.source_format,
                    evidence.activity_id_set_fingerprint,
                    evidence.wbs_fingerprint,
                    evidence.relationship_graph_fingerprint,
                    evidence.import_id,
                    evidence.schedule_version_key,
                    evidence.import_id,
                    evidence.schedule_version_key,
                    json.dumps(observed_evidence, sort_keys=True, default=str),
                ),
            )
        row = conn.execute(
            "SELECT * FROM schedule_identities WHERE schedule_identity_key=?",
            (identity_key,),
        ).fetchone()
        return dict(row)

    def _insert_match(
        self,
        conn: sqlite3.Connection,
        identity_key: str,
        evidence: ScheduleIdentityEvidence,
        decision: dict[str, Any],
        observed_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "match_id": f"sim-{uuid.uuid4().hex}",
            "schedule_identity_key": identity_key,
            "schedule_version_key": evidence.schedule_version_key,
            "import_id": evidence.import_id,
            "project_key": evidence.project_key,
            "source_system": evidence.source_system,
            "source_format": evidence.source_format,
            "source_filename_redacted": evidence.source_filename_redacted,
            "normalized_source_project_id": evidence.normalized_source_project_id,
            "normalized_source_project_name": evidence.normalized_source_project_name,
            "activity_id_set_fingerprint": evidence.activity_id_set_fingerprint,
            "wbs_fingerprint": evidence.wbs_fingerprint,
            "relationship_graph_fingerprint": evidence.relationship_graph_fingerprint,
            "activity_count": evidence.activity_count,
            "relationship_count": evidence.relationship_count,
            "wbs_count": evidence.wbs_count,
            "match_type": decision["match_type"],
            "match_status": decision["match_status"],
            "match_rule": decision["match_rule"],
            "confidence_score": decision["confidence_score"],
            "requires_review": decision["requires_review"],
            "no_match_reason": decision.get("no_match_reason"),
            "candidate_count": decision["candidate_count"],
            "matched_existing_identity_key": decision.get("matched_existing_identity_key"),
            "matched_prior_schedule_version_key": decision.get(
                "matched_prior_schedule_version_key"
            ),
            "winning_candidate_schedule_version_key": decision.get(
                "winning_candidate_schedule_version_key"
            ),
            "evidence_json": json.dumps(observed_evidence, sort_keys=True, default=str),
        }
        cols = list(row.keys())
        conn.execute(
            f"INSERT INTO schedule_version_identity_matches ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            tuple(row[c] for c in cols),
        )
        return row


def parse_schedule_version_data_date(schedule_version_key: str) -> datetime | None:
    parts = str(schedule_version_key or "").split("|")
    if len(parts) < 3:
        return None
    raw = parts[2][:10]
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
