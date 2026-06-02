"""Phase 08A Output Evaluation Agent (A05) persistence (Prompt 12).

Writes a metadata-only evaluation row into the V26 ``second_brain_evaluation_runs`` table
(1:1 with the repo ``evaluation_criteria_contract`` required_fields). The table enforces
four ``CHECK(col = 0)`` no-raw / no-writeback guard columns; this writer leaves them at 0
and persists only the checklist (booleans), counts, score, pass flag, review tier/status,
and degradation mode. The row ``review_status`` is the operator-review state of the
evaluation record itself (defaults ``pending_review``) — never the adapter's review_status,
whose vocabulary differs. Mirrors ``research/store.py::write_research_packet_receipt``.
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
    from .models import EvaluationPreview


def write_evaluation_run(
    *,
    evaluation: EvaluationPreview,
    target_kind: str,
    target_id: str,
    research_packet_id: str | None = None,
    confidence_class: str | None = None,
    review_tier_reason_code: str | None = None,
    degradation_mode: str | None = None,
    mode: str = "dry_run",
    db_path: str | None = None,
) -> str:
    """Insert one evaluation row; returns the generated ``evaluation_run_id``.

    Local-only, additive, metadata-only. Guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V26 table exists (idempotent)

    evaluation_run_id = uuid.uuid4().hex
    checklist_json = json.dumps(evaluation.checklist, sort_keys=True)

    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_evaluation_runs
                (evaluation_run_id, mode, target_kind, target_id, research_packet_id,
                 checklist_json, checklist_total, checklist_passed, score, passed,
                 confidence_class, review_tier, review_tier_reason_code, review_status,
                 degradation_mode, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?)
            """,
            (
                evaluation_run_id,
                mode,
                target_kind,
                target_id,
                research_packet_id,
                checklist_json,
                evaluation.checklist_total,
                evaluation.checklist_passed,
                evaluation.score,
                1 if evaluation.passed else 0,
                confidence_class,
                evaluation.review_tier,
                review_tier_reason_code,
                degradation_mode,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return evaluation_run_id


def read_latest_evaluation_runs(
    *, db_path: str | None = None, target_kind: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent evaluation-run rows (metadata only)."""
    conn = get_connection(Path(db_path) if db_path is not None else None)
    if target_kind is None:
        cur = conn.execute(
            """
            SELECT evaluation_run_id, mode, target_kind, target_id, research_packet_id,
                   checklist_total, checklist_passed, score, passed, review_tier,
                   review_status, degradation_mode, created_utc
            FROM second_brain_evaluation_runs
            ORDER BY created_utc DESC, evaluation_run_id DESC
            LIMIT ?
            """,
            (limit,),
        )
    else:
        cur = conn.execute(
            """
            SELECT evaluation_run_id, mode, target_kind, target_id, research_packet_id,
                   checklist_total, checklist_passed, score, passed, review_tier,
                   review_status, degradation_mode, created_utc
            FROM second_brain_evaluation_runs
            WHERE target_kind = ?
            ORDER BY created_utc DESC, evaluation_run_id DESC
            LIMIT ?
            """,
            (target_kind, limit),
        )
    return [dict(row) for row in cur.fetchall()]
