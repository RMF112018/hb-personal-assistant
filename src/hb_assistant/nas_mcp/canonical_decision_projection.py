"""Read-time projection of promoted canonical artifacts onto the decision-memory read surfaces (Defect 5).

Promotion (``artifact_promotion.promote_bundle``) writes ``pa_canonical_artifacts``; the N8C-8 decision/
preference/open-loop read tools read only the ``assistant_*_records`` tables — two disjoint table families,
and under the internet-facing profile they live in two different DBs (the read-only snapshot vs the writable
workspace DB). So a decision a client promotes never appears in ``assistant_list_decisions``.

This module supplies a **read-only projection**: it reads the canonical artifacts of a given kind from the
correct DB (workspace DB under the read-only profile, else the ambient managed DB) and maps them onto the
record shape the read tools return, tagged ``record_source="canonical_artifact"``. No writes, so the
decision-memory repository stays the sole *writer* of the V104 tables. Composes with the future
workspace→live merge job (both read ``pa_canonical_artifacts``).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from hb_assistant.obsidian_mcp.decision_memory_repository import record_matches_list_query

# kind -> (pk column, type column, text column, normalized column) on the record shape.
_KIND_FIELDS: dict[str, tuple[str, str, str, str]] = {
    "decision": ("decision_id", "decision_type", "decision_text", "normalized_decision"),
    "preference": ("preference_id", "preference_type", "preference_text", "normalized_preference"),
    "open_loop": ("open_loop_id", "open_loop_type", "open_loop_text", "normalized_action"),
}

_CANONICAL_COLS = (
    "canonical_id", "artifact_type", "title", "summary", "domain", "status", "source_client",
    "source_session_id", "source_proposal_id", "promotion_receipt_id", "supersedes_canonical_id",
    "vault_path", "content_hash", "created_at", "updated_at", "promoted_at",
)


def _canonical_db_path(cfg: Any) -> str:
    """The DB holding pa_canonical_artifacts: the writable workspace DB under the read-only profile
    (where promotion writes), else the ambient managed DB."""
    from hb_assistant.store.connection import db_readonly  # noqa: PLC0415

    if db_readonly():
        from hb_assistant.store.workspace import workspace_db_path  # noqa: PLC0415

        return str(workspace_db_path())
    return str(cfg.db_path)


def _table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pa_canonical_artifacts' LIMIT 1"
    ).fetchone()
    return row is not None


def _project(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    pk, type_col, text_col, norm_col = _KIND_FIELDS[kind]
    text = row.get("summary") or row.get("title")
    return {
        pk: row["canonical_id"],
        "identity_key": row.get("supersedes_canonical_id") or row["canonical_id"],
        type_col: "canonical_artifact",
        text_col: text,
        "normalized_subject": row.get("title"),
        norm_col: row.get("summary"),
        "domain": row.get("domain"),
        "status": row.get("status"),
        "confidence": None,
        "source_id": row.get("source_session_id") or row.get("source_proposal_id"),
        "note_rel_path": row.get("vault_path"),
        "evidence_excerpt": None,
        "observed_at": row.get("promoted_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "promotion_receipt_id": row.get("promotion_receipt_id"),
        "canonical_id": row["canonical_id"],
        "metadata_json": json.dumps(
            {"content_hash": row.get("content_hash"), "source_client": row.get("source_client")},
            sort_keys=True,
        ),
        "record_source": "canonical_artifact",
    }


def project_canonical_records(cfg: Any, kind: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Active (``status='canonical'``) promoted artifacts of ``kind``, projected onto the record shape."""
    if kind not in _KIND_FIELDS:
        return []
    path = _canonical_db_path(cfg)
    # Plain mode=ro (NOT immutable): the workspace/managed DB is a LIVE file written by promotion, so
    # its WAL must be consulted — an immutable open would miss just-promoted rows still in the WAL. Its
    # containing dir is writable (RW workspace mount / local managed dir), so mode=ro opens cleanly.
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
    except sqlite3.Error:
        return []
    try:
        conn.execute("PRAGMA query_only=ON")
        if not _table_exists(conn):
            return []
        rows = conn.execute(
            f"SELECT {', '.join(_CANONICAL_COLS)} FROM pa_canonical_artifacts "
            "WHERE artifact_type=? AND status='canonical' "
            "ORDER BY promoted_at DESC, canonical_id DESC LIMIT ?",
            (kind, max(1, min(int(limit), 200))),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [_project(kind, dict(zip(_CANONICAL_COLS, r, strict=True))) for r in rows]


def project_canonical_record(cfg: Any, kind: str, record_id: str) -> dict[str, Any] | None:
    """Single projected canonical artifact by its canonical_id, or None."""
    for rec in project_canonical_records(cfg, kind, limit=200):
        if rec.get("canonical_id") == record_id:
            return rec
    return None


def filter_records_by_query(records: list[dict[str, Any]], kind: str,
                            query: str | None) -> list[dict[str, Any]]:
    """Apply the same bounded topical filter used by decision-memory list tools."""
    return [r for r in records if record_matches_list_query(kind, r, query)]


def merge_records(native: list[dict[str, Any]], projected: list[dict[str, Any]], *, pk: str,
                  status: str | None, limit: int) -> list[dict[str, Any]]:
    """Native extracted records first, then any projected canonical rows not already present (by pk).

    A non-canonical ``status`` filter drops projected rows (their status is always ``canonical``) so a
    client filtering e.g. ``status='candidate'`` doesn't see canonical artifacts spuriously.
    """
    if status is not None and status != "canonical":
        projected = []
    seen = {r.get(pk) for r in native}
    merged = list(native) + [p for p in projected if p.get(pk) not in seen]
    return merged[: max(1, int(limit))]
