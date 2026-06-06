"""Phase 08A memory + operator-preference receipt store (Prompt 10).

Metadata-only writers over the V26 memory / preference / feedback tables. Every table
enforces ``CHECK(raw_prompt_persisted = 0)`` / ``CHECK(raw_response_persisted = 0)`` (and
where present ``retrieved_context_persisted``) at the DB layer; these writers leave them
at 0 and persist only redacted statements, source-ref metadata, classes, and counts.
Mirrors ``second_brain/store.py``. All idempotent via the migrator.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator

if TYPE_CHECKING:
    from .models import (
        MemoryCandidate,
        MemoryItem,
        MemoryReview,
        OperatorFeedback,
        OperatorPreference,
        QualitySignal,
    )


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(db_path: str | None):  # type: ignore[no-untyped-def]
    SQLiteMigrator(db_path).apply()
    return get_connection(Path(db_path) if db_path is not None else None)


def write_memory_candidate(candidate: MemoryCandidate, *, db_path: str | None = None) -> str:
    conn = _conn(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO memory_update_candidates
                (candidate_id, proposed_memory_type, statement_redacted, project_key, origin_id,
                 provenance_class, confidence_class, review_required, review_tier,
                 review_tier_reason_code, sensitivity_class, source_refs_json, status, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.proposed_memory_type,
                candidate.statement_redacted,
                candidate.project_key,
                candidate.origin_id,
                candidate.provenance_class,
                candidate.confidence_class,
                1 if candidate.review_required else 0,
                candidate.review_tier,
                candidate.review_tier_reason_code,
                candidate.sensitivity_class,
                json.dumps(candidate.source_refs, sort_keys=True),
                candidate.status,
                _utc(),
            ),
        )
    return candidate.candidate_id


def set_candidate_status(candidate_id: str, status: str, *, db_path: str | None = None) -> None:
    conn = _conn(db_path)
    with transaction(conn):
        conn.execute(
            "UPDATE memory_update_candidates SET status = ? WHERE candidate_id = ?",
            (status, candidate_id),
        )


def set_memory_item_status(
    memory_id: str,
    *,
    review_status: str | None = None,
    supersedes_memory_id: str | None = None,
    db_path: str | None = None,
) -> None:
    """Metadata-only update of an accepted memory item's status / supersession linkage.

    Only the provided fields are changed (``updated_utc`` is always refreshed). Never touches raw /
    guard columns; the ``review_status`` CHECK enforces the valid enum. Transition policy is enforced
    by the caller (``quality_controls.supersede_accepted_memory``)."""
    sets: list[str] = []
    params: list[Any] = []
    if review_status is not None:
        sets.append("review_status = ?")
        params.append(review_status)
    if supersedes_memory_id is not None:
        sets.append("supersedes_memory_id = ?")
        params.append(supersedes_memory_id)
    if not sets:
        return
    sets.append("updated_utc = ?")
    params.append(_utc())
    params.append(memory_id)
    conn = _conn(db_path)
    with transaction(conn):
        conn.execute(
            f"UPDATE long_term_memory_items SET {', '.join(sets)} WHERE memory_id = ?",
            tuple(params),
        )


def write_memory_review(review: MemoryReview, *, db_path: str | None = None) -> str:
    conn = _conn(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO memory_update_reviews
                (review_id, candidate_id, decision, reviewer_ref, decision_reason_redacted,
                 reviewed_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                review.review_id,
                review.candidate_id,
                review.decision,
                review.reviewer_ref,
                review.decision_reason_redacted,
                _utc(),
            ),
        )
    return review.review_id


def write_memory_item(item: MemoryItem, *, db_path: str | None = None) -> str:
    conn = _conn(db_path)
    now = _utc()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO long_term_memory_items
                (memory_id, memory_type, statement_redacted, project_key, entity_key, origin_id,
                 provenance_class, confidence_class, review_status, sensitivity_class,
                 supersedes_memory_id, created_utc, updated_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.memory_id,
                item.memory_type,
                item.statement_redacted,
                item.project_key,
                item.entity_key,
                item.origin_id,
                item.provenance_class,
                item.confidence_class,
                item.review_status,
                item.sensitivity_class,
                item.supersedes_memory_id,
                now,
                now,
            ),
        )
        for ref in item.source_refs:
            conn.execute(
                """
                INSERT INTO long_term_memory_source_refs
                    (memory_source_ref_id, memory_id, source_family, source_ref, evidence_trail_id,
                     confidence_class, review_required)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    item.memory_id,
                    ref.get("source_family", "unknown"),
                    ref.get("source_ref", ""),
                    ref.get("evidence_ref") or ref.get("evidence_trail_id"),
                    ref.get("confidence_class"),
                    0,
                ),
            )
    return item.memory_id


def write_quality_signal(signal: QualitySignal, *, db_path: str | None = None) -> str:
    conn = _conn(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO long_term_memory_quality_signals
                (signal_id, memory_id, signal_type, origin_id, provenance_class, quality_score,
                 freshness_class, conflict_flag, feedback_id, review_required, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.signal_id,
                signal.memory_id,
                signal.signal_type,
                signal.origin_id,
                signal.provenance_class,
                signal.quality_score,
                signal.freshness_class,
                1 if signal.conflict_flag else 0,
                signal.feedback_id,
                1 if signal.review_required else 0,
                _utc(),
            ),
        )
    return signal.signal_id


def write_operator_feedback(feedback: OperatorFeedback, *, db_path: str | None = None) -> str:
    conn = _conn(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_operator_feedback
                (feedback_id, target_kind, target_id, origin_id, feedback_class, rating,
                 reason_redacted, review_tier, review_tier_reason_code, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback.feedback_id,
                feedback.target_kind,
                feedback.target_id,
                feedback.origin_id,
                feedback.feedback_class,
                feedback.rating,
                feedback.reason_redacted,
                feedback.review_tier,
                feedback.review_tier_reason_code,
                _utc(),
            ),
        )
    return feedback.feedback_id


def upsert_operator_preference(pref: OperatorPreference, *, db_path: str | None = None) -> str:
    conn = _conn(db_path)
    now = _utc()
    scope_key = pref.scope_key or ""  # coerce NULL so the UNIQUE constraint dedupes
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_operator_preference_profiles
                (preference_id, scope, scope_key, preference_key, preference_value_redacted,
                 confidence_class, signal_count, source_feedback_refs_json, review_status,
                 created_utc, updated_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope, scope_key, preference_key) DO UPDATE SET
                preference_value_redacted = excluded.preference_value_redacted,
                confidence_class = excluded.confidence_class,
                signal_count = second_brain_operator_preference_profiles.signal_count + 1,
                source_feedback_refs_json = excluded.source_feedback_refs_json,
                review_status = excluded.review_status,
                updated_utc = excluded.updated_utc
            """,
            (
                pref.preference_id,
                pref.scope,
                scope_key,
                pref.preference_key,
                pref.preference_value_redacted,
                pref.confidence_class,
                pref.signal_count,
                json.dumps(pref.source_feedback_refs, sort_keys=True),
                pref.review_status,
                now,
                now,
            ),
        )
    return pref.preference_id


def _rows(db_path: str | None, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def read_memory_candidates(
    *, db_path: str | None = None, status: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    if status is not None:
        return _rows(
            db_path,
            "SELECT candidate_id, proposed_memory_type, statement_redacted, project_key, origin_id, "
            "confidence_class, review_required, review_tier, review_tier_reason_code, "
            "sensitivity_class, status, created_utc FROM memory_update_candidates "
            "WHERE status = ? ORDER BY created_utc DESC LIMIT ?",
            (status, limit),
        )
    return _rows(
        db_path,
        "SELECT candidate_id, proposed_memory_type, statement_redacted, project_key, origin_id, "
        "confidence_class, review_required, review_tier, review_tier_reason_code, "
        "sensitivity_class, status, created_utc FROM memory_update_candidates "
        "ORDER BY created_utc DESC LIMIT ?",
        (limit,),
    )


def read_memory_candidate(
    candidate_id: str, *, db_path: str | None = None
) -> dict[str, Any] | None:
    """Return one candidate row (incl. source_refs_json) or None (schema ensured)."""
    conn = _conn(db_path)  # ensure V26 schema exists (idempotent) before reading
    row = conn.execute(
        "SELECT candidate_id, proposed_memory_type, statement_redacted, project_key, origin_id, "
        "provenance_class, confidence_class, review_required, review_tier, review_tier_reason_code, "
        "sensitivity_class, source_refs_json, status FROM memory_update_candidates "
        "WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def read_operator_preferences(
    *, db_path: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        "SELECT preference_id, scope, scope_key, preference_key, preference_value_redacted, "
        "confidence_class, signal_count, review_status, created_utc, updated_utc "
        "FROM second_brain_operator_preference_profiles ORDER BY updated_utc DESC LIMIT ?",
        (limit,),
    )
