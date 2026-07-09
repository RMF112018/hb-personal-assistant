"""Persistence for the NAS Source-Structure Layered Index (V115).

Reads and writes SQLite rows only — it NEVER touches the filesystem and NEVER runs a live scan.
Writes are used exclusively by out-of-band CLI/scheduled jobs; reads back the bounded surfaces the
service/API/MCP layers expose. Stable IDs are content hashes so re-ingest is idempotent.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.obsidian_mcp.source_structure_models import (
    FolderClassification,
    SourceStructureRoot,
    clamp_limit,
)
from hb_assistant.store.connection import borrow_connection, transaction


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sid(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]


def folder_id_for(root_key: str, rel_path: str) -> str:
    return _sid("folder", root_key, rel_path)


def entity_id_for(entity_type: str, canonical_key: str) -> str:
    return _sid("entity", entity_type, canonical_key)


def _b(value: bool) -> int:
    return 1 if value else 0


def _json_or_none(value: object) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"))


class SourceStructureRepository:
    """CRUD + bounded reads over the ``source_structure_*`` tables."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None

    # -- writes (out-of-band only) -------------------------------------------------------------
    def upsert_root(
        self,
        root: SourceStructureRoot,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                INSERT INTO source_structure_roots (
                  root_key, display_name, root_class, trust_tier, index_policy, default_search_rank,
                  is_sensitive, is_generated_output, is_backup_mirror, is_active, last_seen_at,
                  last_indexed_at, folder_count, file_count, noise_count, max_depth, notes,
                  created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(root_key) DO UPDATE SET
                  display_name=excluded.display_name, root_class=excluded.root_class,
                  trust_tier=excluded.trust_tier, index_policy=excluded.index_policy,
                  default_search_rank=excluded.default_search_rank, is_sensitive=excluded.is_sensitive,
                  is_generated_output=excluded.is_generated_output,
                  is_backup_mirror=excluded.is_backup_mirror, is_active=excluded.is_active,
                  last_seen_at=excluded.last_seen_at, last_indexed_at=excluded.last_indexed_at,
                  folder_count=excluded.folder_count, file_count=excluded.file_count,
                  noise_count=excluded.noise_count, max_depth=excluded.max_depth,
                  notes=excluded.notes, updated_at=excluded.updated_at
                """,
                (
                    root.root_key, root.display_name, root.root_class, root.trust_tier,
                    root.index_policy, root.default_search_rank, _b(root.is_sensitive),
                    _b(root.is_generated_output), _b(root.is_backup_mirror), _b(root.is_active),
                    root.last_seen_at, root.last_indexed_at, root.folder_count, root.file_count,
                    root.noise_count, root.max_depth, root.notes, now, now,
                ),
            )

    def upsert_folder(
        self,
        *,
        root_key: str,
        rel_path: str,
        name: str,
        depth: int,
        parent_rel_path: str | None,
        classification: FolderClassification,
        child_folder_count: int,
        file_count: int,
        dominant_extensions: list[str],
        sample_names: list[str],
        fingerprint: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        now = _utc_now()
        fid = folder_id_for(root_key, rel_path)
        parent_id = (
            folder_id_for(root_key, parent_rel_path) if parent_rel_path is not None else None
        )
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                INSERT INTO source_structure_folders (
                  folder_id, root_key, parent_folder_id, rel_path, name, depth, folder_class,
                  doc_family, trust_tier, search_rank, is_noise, is_backup_mirror,
                  is_generated_output, is_sensitive, is_project_candidate, project_number,
                  project_name_hint, child_folder_count, file_count, dominant_extensions_json,
                  sample_names_json, fingerprint, last_seen_at, last_indexed_at,
                  classification_source, classification_confidence, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(folder_id) DO UPDATE SET
                  parent_folder_id=excluded.parent_folder_id, name=excluded.name,
                  depth=excluded.depth, folder_class=excluded.folder_class,
                  doc_family=excluded.doc_family, trust_tier=excluded.trust_tier,
                  search_rank=excluded.search_rank, is_noise=excluded.is_noise,
                  is_backup_mirror=excluded.is_backup_mirror,
                  is_generated_output=excluded.is_generated_output, is_sensitive=excluded.is_sensitive,
                  is_project_candidate=excluded.is_project_candidate,
                  project_number=excluded.project_number, project_name_hint=excluded.project_name_hint,
                  child_folder_count=excluded.child_folder_count, file_count=excluded.file_count,
                  dominant_extensions_json=excluded.dominant_extensions_json,
                  sample_names_json=excluded.sample_names_json, fingerprint=excluded.fingerprint,
                  last_seen_at=excluded.last_seen_at, last_indexed_at=excluded.last_indexed_at,
                  classification_source=excluded.classification_source,
                  classification_confidence=excluded.classification_confidence,
                  updated_at=excluded.updated_at
                """,
                (
                    fid, root_key, parent_id, rel_path, name, depth, classification.folder_class,
                    classification.doc_family, classification.trust_tier, classification.search_rank,
                    _b(classification.is_noise), _b(classification.is_backup_mirror),
                    _b(classification.is_generated_output), _b(classification.is_sensitive),
                    _b(classification.is_project_candidate), classification.project_number,
                    classification.project_name_hint, child_folder_count, file_count,
                    _json_or_none(dominant_extensions), _json_or_none(sample_names), fingerprint,
                    now, now, classification.classification_source,
                    classification.classification_confidence, now, now,
                ),
            )
        return fid

    def upsert_entity(
        self,
        *,
        entity_type: str,
        canonical_key: str,
        display_name: str | None = None,
        project_number: str | None = None,
        project_name: str | None = None,
        confidence: float = 0.0,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        now = _utc_now()
        eid = entity_id_for(entity_type, canonical_key)
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                INSERT INTO source_structure_entities (
                  entity_id, entity_type, canonical_key, display_name, project_number, project_name,
                  confidence, first_seen_at, last_seen_at, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(entity_type, canonical_key) DO UPDATE SET
                  display_name=COALESCE(excluded.display_name, source_structure_entities.display_name),
                  project_number=COALESCE(excluded.project_number, source_structure_entities.project_number),
                  project_name=COALESCE(excluded.project_name, source_structure_entities.project_name),
                  confidence=MAX(excluded.confidence, source_structure_entities.confidence),
                  last_seen_at=excluded.last_seen_at, updated_at=excluded.updated_at
                """,
                (eid, entity_type, canonical_key, display_name, project_number, project_name,
                 confidence, now, now, now, now),
            )
        return eid

    def link_entity_folder(
        self,
        *,
        entity_id: str,
        folder_id: str,
        relationship_type: str,
        confidence: float = 0.0,
        evidence: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                INSERT INTO source_structure_entity_folders (
                  entity_id, folder_id, relationship_type, confidence, evidence_json,
                  created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(entity_id, folder_id, relationship_type) DO UPDATE SET
                  confidence=MAX(excluded.confidence, source_structure_entity_folders.confidence),
                  evidence_json=excluded.evidence_json, updated_at=excluded.updated_at
                """,
                (entity_id, folder_id, relationship_type, confidence,
                 _json_or_none(evidence or []), now, now),
            )

    def upsert_summary(
        self,
        *,
        subject_type: str,
        subject_id: str,
        summary_text: str,
        summary_kind: str = "deterministic",
        input_fingerprint: str | None = None,
        confidence: float = 0.0,
        model_name: str | None = None,
        prompt_version: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        now = _utc_now()
        sid = _sid("summary", subject_type, subject_id, summary_kind)
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                INSERT INTO source_structure_summaries (
                  summary_id, subject_type, subject_id, summary_text, summary_kind, model_name,
                  prompt_version, input_fingerprint, confidence, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(subject_type, subject_id, summary_kind) DO UPDATE SET
                  summary_text=excluded.summary_text, model_name=excluded.model_name,
                  prompt_version=excluded.prompt_version, input_fingerprint=excluded.input_fingerprint,
                  confidence=excluded.confidence, updated_at=excluded.updated_at
                """,
                (sid, subject_type, subject_id, summary_text, summary_kind, model_name,
                 prompt_version, input_fingerprint, confidence, now, now),
            )
        return sid

    def replace_hints(
        self,
        query_family: str,
        hints: list[dict],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Replace all hints for a query_family (idempotent regeneration)."""
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                "DELETE FROM source_structure_hints WHERE query_family = ?", (query_family,)
            )
            for h in hints:
                hid = _sid("hint", query_family, h.get("hint_type", ""), str(h.get("rank", 0)),
                           h.get("root_key") or "", h.get("folder_id") or "")
                c.execute(
                    """
                    INSERT INTO source_structure_hints (
                      hint_id, hint_type, query_family, root_key, folder_id, entity_id, rank,
                      hint_text, evidence_json, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(hint_id) DO UPDATE SET
                      hint_text=excluded.hint_text, rank=excluded.rank,
                      evidence_json=excluded.evidence_json, updated_at=excluded.updated_at
                    """,
                    (hid, h["hint_type"], query_family, h.get("root_key"), h.get("folder_id"),
                     h.get("entity_id"), h.get("rank", 0), h["hint_text"],
                     _json_or_none(h.get("evidence") or []), now, now),
                )

    def replace_findings(
        self, findings: list[dict], *, conn: sqlite3.Connection | None = None
    ) -> None:
        """Replace the open finding set (quality recomputation is idempotent)."""
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute("DELETE FROM source_structure_findings WHERE status = 'open'")
            for f in findings:
                fid = _sid("finding", f["finding_type"], f.get("root_key") or "",
                           f.get("folder_id") or "", f.get("entity_id") or "")
                c.execute(
                    """
                    INSERT INTO source_structure_findings (
                      finding_id, finding_type, severity, root_key, folder_id, entity_id, title,
                      details, evidence_json, status, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(finding_id) DO UPDATE SET
                      severity=excluded.severity, title=excluded.title, details=excluded.details,
                      evidence_json=excluded.evidence_json, status='open', updated_at=excluded.updated_at
                    """,
                    (fid, f["finding_type"], f.get("severity", "info"), f.get("root_key"),
                     f.get("folder_id"), f.get("entity_id"), f["title"], f.get("details"),
                     _json_or_none(f.get("evidence") or []), "open", now, now),
                )

    def start_run(
        self, run_id: str, run_type: str, *, roots: list[str] | None = None,
        options: dict | None = None, conn: sqlite3.Connection | None = None,
    ) -> None:
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                INSERT INTO source_structure_runs (
                  run_id, run_type, started_at, status, roots_json, options_json, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (run_id, run_type, now, "running", _json_or_none(roots),
                 _json_or_none(options), now, now),
            )

    def finish_run(
        self, run_id: str, status: str, *, counts: dict | None = None,
        error_text: str | None = None, conn: sqlite3.Connection | None = None,
    ) -> None:
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                """
                UPDATE source_structure_runs
                SET status=?, finished_at=?, counts_json=?, error_text=?, updated_at=?
                WHERE run_id=?
                """,
                (status, now, _json_or_none(counts), error_text, now, run_id),
            )

    # -- reads (bounded) -----------------------------------------------------------------------
    def status(self, *, conn: sqlite3.Connection | None = None) -> dict:
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            def _count(tbl: str) -> int:
                return int(c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])

            last = c.execute(
                "SELECT run_id, run_type, status, started_at, finished_at "
                "FROM source_structure_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            return {
                "root_count": _count("source_structure_roots"),
                "folder_count": _count("source_structure_folders"),
                "entity_count": _count("source_structure_entities"),
                "summary_count": _count("source_structure_summaries"),
                "hint_count": _count("source_structure_hints"),
                "finding_count": _count(
                    "source_structure_findings"
                ),
                "open_finding_count": int(
                    c.execute(
                        "SELECT COUNT(*) FROM source_structure_findings WHERE status='open'"
                    ).fetchone()[0]
                ),
                "last_run": (
                    {"run_id": last[0], "run_type": last[1], "status": last[2],
                     "started_at": last[3], "finished_at": last[4]} if last else None
                ),
            }

    def list_roots(self, *, limit: int | None = None,
                   conn: sqlite3.Connection | None = None) -> list[dict]:
        n = clamp_limit(limit)
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                """
                SELECT root_key, display_name, root_class, trust_tier, index_policy,
                       default_search_rank, is_sensitive, is_generated_output, is_backup_mirror,
                       is_active, folder_count, file_count, noise_count, max_depth, last_indexed_at
                FROM source_structure_roots
                ORDER BY default_search_rank ASC, root_key ASC
                LIMIT ?
                """,
                (n,),
            ).fetchall()
        return [
            {
                "root_key": r[0], "display_name": r[1], "root_class": r[2], "trust_tier": r[3],
                "index_policy": r[4], "default_search_rank": r[5], "is_sensitive": bool(r[6]),
                "is_generated_output": bool(r[7]), "is_backup_mirror": bool(r[8]),
                "is_active": bool(r[9]), "folder_count": r[10], "file_count": r[11],
                "noise_count": r[12], "max_depth": r[13], "last_indexed_at": r[14],
            }
            for r in rows
        ]

    def _folder_row(self, r: tuple) -> dict:
        return {
            "folder_id": r[0], "root_key": r[1], "parent_folder_id": r[2], "rel_path": r[3],
            "name": r[4], "depth": r[5], "folder_class": r[6], "doc_family": r[7],
            "trust_tier": r[8], "search_rank": r[9], "is_noise": bool(r[10]),
            "is_backup_mirror": bool(r[11]), "is_generated_output": bool(r[12]),
            "is_sensitive": bool(r[13]), "is_project_candidate": bool(r[14]),
            "project_number": r[15], "project_name_hint": r[16], "child_folder_count": r[17],
            "file_count": r[18],
            "dominant_extensions": json.loads(r[19]) if r[19] else [],
            "sample_names": json.loads(r[20]) if r[20] else [],
            "classification_source": r[21], "classification_confidence": r[22],
        }

    _FOLDER_COLS = (
        "folder_id, root_key, parent_folder_id, rel_path, name, depth, folder_class, doc_family, "
        "trust_tier, search_rank, is_noise, is_backup_mirror, is_generated_output, is_sensitive, "
        "is_project_candidate, project_number, project_name_hint, child_folder_count, file_count, "
        "dominant_extensions_json, sample_names_json, classification_source, classification_confidence"
    )

    def list_folders(
        self,
        *,
        root_key: str | None = None,
        parent_folder_id: str | None = None,
        depth: int | None = None,
        folder_class: str | None = None,
        doc_family: str | None = None,
        project_number: str | None = None,
        include_noise: bool = False,
        limit: int | None = None,
        offset: int = 0,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[list[dict], int]:
        n = clamp_limit(limit)
        where: list[str] = []
        params: list[object] = []
        if root_key:
            where.append("root_key = ?")
            params.append(root_key)
        if parent_folder_id is not None:
            where.append("parent_folder_id = ?")
            params.append(parent_folder_id)
        if depth is not None:
            where.append("depth = ?")
            params.append(depth)
        if folder_class:
            where.append("folder_class = ?")
            params.append(folder_class)
        if doc_family:
            where.append("doc_family = ?")
            params.append(doc_family)
        if project_number:
            where.append("project_number = ?")
            params.append(project_number)
        if not include_noise:
            where.append("is_noise = 0")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            total = int(
                c.execute(
                    f"SELECT COUNT(*) FROM source_structure_folders{clause}", params
                ).fetchone()[0]
            )
            rows = c.execute(
                f"SELECT {self._FOLDER_COLS} FROM source_structure_folders{clause} "
                "ORDER BY search_rank ASC, rel_path ASC LIMIT ? OFFSET ?",
                (*params, n, max(0, offset)),
            ).fetchall()
        return [self._folder_row(r) for r in rows], total

    def get_folder(self, folder_id: str, *,
                   conn: sqlite3.Connection | None = None) -> dict | None:
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            r = c.execute(
                f"SELECT {self._FOLDER_COLS} FROM source_structure_folders WHERE folder_id = ?",
                (folder_id,),
            ).fetchone()
        return self._folder_row(r) if r else None

    def child_class_counts(self, folder_id: str, *,
                           conn: sqlite3.Connection | None = None) -> dict[str, int]:
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                "SELECT folder_class, COUNT(*) FROM source_structure_folders "
                "WHERE parent_folder_id = ? GROUP BY folder_class",
                (folder_id,),
            ).fetchall()
        return {r[0]: int(r[1]) for r in rows}

    def get_summary(self, subject_type: str, subject_id: str, *,
                    conn: sqlite3.Connection | None = None) -> dict | None:
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            r = c.execute(
                "SELECT summary_text, summary_kind, confidence, updated_at "
                "FROM source_structure_summaries WHERE subject_type=? AND subject_id=? "
                "ORDER BY CASE summary_kind WHEN 'manual' THEN 0 WHEN 'ollama' THEN 1 ELSE 2 END "
                "LIMIT 1",
                (subject_type, subject_id),
            ).fetchone()
        if not r:
            return None
        return {"summary_text": r[0], "summary_kind": r[1], "confidence": r[2], "updated_at": r[3]}

    def list_hints(self, *, query_family: str | None = None, limit: int | None = None,
                   conn: sqlite3.Connection | None = None) -> list[dict]:
        n = clamp_limit(limit)
        where = " WHERE query_family = ?" if query_family else ""
        params: tuple = (query_family,) if query_family else ()
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                "SELECT hint_type, query_family, root_key, folder_id, entity_id, rank, hint_text, "
                f"evidence_json FROM source_structure_hints{where} "
                "ORDER BY rank ASC LIMIT ?",
                (*params, n),
            ).fetchall()
        return [
            {"hint_type": r[0], "query_family": r[1], "root_key": r[2], "folder_id": r[3],
             "entity_id": r[4], "rank": r[5], "hint_text": r[6],
             "evidence": json.loads(r[7]) if r[7] else []}
            for r in rows
        ]

    def project_folders(self, project_number: str, *, limit: int | None = None,
                        conn: sqlite3.Connection | None = None) -> list[dict]:
        n = clamp_limit(limit)
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                f"SELECT {self._FOLDER_COLS} FROM source_structure_folders "
                "WHERE project_number = ? ORDER BY search_rank ASC, depth ASC LIMIT ?",
                (project_number, n),
            ).fetchall()
        return [self._folder_row(r) for r in rows]

    def list_findings(
        self, *, severity: str | None = None, finding_type: str | None = None,
        status: str | None = "open", limit: int | None = None, offset: int = 0,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[list[dict], int]:
        n = clamp_limit(limit)
        where: list[str] = []
        params: list[object] = []
        if severity:
            where.append("severity = ?")
            params.append(severity)
        if finding_type:
            where.append("finding_type = ?")
            params.append(finding_type)
        if status:
            where.append("status = ?")
            params.append(status)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            total = int(
                c.execute(
                    f"SELECT COUNT(*) FROM source_structure_findings{clause}", params
                ).fetchone()[0]
            )
            rows = c.execute(
                "SELECT finding_id, finding_type, severity, root_key, folder_id, entity_id, title, "
                f"details, evidence_json, status FROM source_structure_findings{clause} "
                "ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, "
                "finding_type ASC LIMIT ? OFFSET ?",
                (*params, n, max(0, offset)),
            ).fetchall()
        items = [
            {"finding_id": r[0], "finding_type": r[1], "severity": r[2], "root_key": r[3],
             "folder_id": r[4], "entity_id": r[5], "title": r[6], "details": r[7],
             "evidence": json.loads(r[8]) if r[8] else [], "status": r[9]}
            for r in rows
        ]
        return items, total

    # -- helpers for quality/scan aggregation --------------------------------------------------
    def all_roots(self, *, conn: sqlite3.Connection | None = None) -> list[dict]:
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                "SELECT root_key, display_name, root_class, trust_tier, default_search_rank, "
                "is_backup_mirror, is_generated_output, folder_count, last_indexed_at, notes "
                "FROM source_structure_roots"
            ).fetchall()
        return [
            {"root_key": r[0], "display_name": r[1], "root_class": r[2], "trust_tier": r[3],
             "default_search_rank": r[4], "is_backup_mirror": bool(r[5]),
             "is_generated_output": bool(r[6]), "folder_count": r[7], "last_indexed_at": r[8],
             "notes": r[9]}
            for r in rows
        ]

    def iter_folders_raw(self, *, conn: sqlite3.Connection | None = None) -> list[dict]:
        """Full folder scan for quality computation (server-side/out-of-band only)."""
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                f"SELECT {self._FOLDER_COLS} FROM source_structure_folders"
            ).fetchall()
        return [self._folder_row(r) for r in rows]

    def update_root_rollups(
        self, root_key: str, *, folder_count: int, file_count: int, noise_count: int,
        max_depth: int, conn: sqlite3.Connection | None = None,
    ) -> None:
        now = _utc_now()
        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_structure_roots SET folder_count=?, file_count=?, noise_count=?, "
                "max_depth=?, last_indexed_at=?, last_seen_at=?, updated_at=? WHERE root_key=?",
                (folder_count, file_count, noise_count, max_depth, now, now, now, root_key),
            )

    # -- V116 operator classification overrides ------------------------------------------------
    _OVERRIDE_COLS = (
        "override_id, target_type, root_key, rel_path, root_class, folder_class, doc_family, "
        "trust_tier, search_rank, is_backup_mirror, is_generated_output, is_sensitive, reason, "
        "created_by, active"
    )

    @staticmethod
    def _override_row(r: tuple) -> dict:
        def _ob(v: object) -> bool | None:
            return None if v is None else bool(v)

        return {
            "override_id": r[0], "target_type": r[1], "root_key": r[2], "rel_path": r[3],
            "root_class": r[4], "folder_class": r[5], "doc_family": r[6], "trust_tier": r[7],
            "search_rank": r[8], "is_backup_mirror": _ob(r[9]), "is_generated_output": _ob(r[10]),
            "is_sensitive": _ob(r[11]), "reason": r[12], "created_by": r[13], "active": bool(r[14]),
        }

    def upsert_override(
        self, *, target_type: str, root_key: str, reason: str, created_by: str,
        rel_path: str = "", active: bool = True, root_class: str | None = None,
        folder_class: str | None = None, doc_family: str | None = None,
        trust_tier: str | None = None, search_rank: int | None = None,
        is_backup_mirror: bool | None = None, is_generated_output: bool | None = None,
        is_sensitive: bool | None = None, conn: sqlite3.Connection | None = None,
    ) -> str:
        """Persist one operator override. Roots use ``rel_path=''``. Requires reason + created_by
        (the CLI fails closed if either is missing). Idempotent per (target_type, root_key, rel_path)."""
        if not reason or not created_by:
            raise ValueError("override requires a non-empty reason and created_by")
        rel = rel_path if target_type == "folder" else ""
        override_id = _sid("override", target_type, root_key, rel)
        now = _utc_now()

        def _fb(v: bool | None) -> int | None:
            return None if v is None else _b(v)

        with borrow_connection(conn, self._db_path) as c, transaction(c):
            c.execute(
                f"""
                INSERT INTO source_structure_overrides ({self._OVERRIDE_COLS}, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(target_type, root_key, rel_path) DO UPDATE SET
                  root_class=excluded.root_class, folder_class=excluded.folder_class,
                  doc_family=excluded.doc_family, trust_tier=excluded.trust_tier,
                  search_rank=excluded.search_rank, is_backup_mirror=excluded.is_backup_mirror,
                  is_generated_output=excluded.is_generated_output, is_sensitive=excluded.is_sensitive,
                  reason=excluded.reason, created_by=excluded.created_by, active=excluded.active,
                  updated_at=excluded.updated_at
                """,
                (override_id, target_type, root_key, rel, root_class, folder_class, doc_family,
                 trust_tier, search_rank, _fb(is_backup_mirror), _fb(is_generated_output),
                 _fb(is_sensitive), reason, created_by, _b(active), now, now),
            )
        return override_id

    def list_overrides(
        self, *, active_only: bool = False, target_type: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict]:
        where: list[str] = []
        params: list[object] = []
        if active_only:
            where.append("active = 1")
        if target_type:
            where.append("target_type = ?")
            params.append(target_type)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                f"SELECT {self._OVERRIDE_COLS} FROM source_structure_overrides{clause} "
                "ORDER BY target_type, root_key, rel_path",
                params,
            ).fetchall()
        return [self._override_row(r) for r in rows]

    def active_overrides_for(self, root_key: str, *,
                             conn: sqlite3.Connection | None = None) -> list[dict]:
        with borrow_connection(conn, self._db_path, readonly=True) as c:
            rows = c.execute(
                f"SELECT {self._OVERRIDE_COLS} FROM source_structure_overrides "
                "WHERE active = 1 AND root_key = ?",
                (root_key,),
            ).fetchall()
        return [self._override_row(r) for r in rows]
