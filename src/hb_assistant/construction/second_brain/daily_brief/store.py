"""Phase 08A daily-brief run store (Prompt 11).

Writes a metadata-only daily-brief run into the existing V26 ``daily_brief_runs`` table
(+ ``daily_brief_source_refs``). Both tables enforce ``CHECK(col = 0)`` no-raw /
no-writeback guard columns; this writer leaves them all at 0 and persists only counts,
classes, the redacted research-packet link, and source-ref identifiers. No output file is
rendered (``output_path_*`` stay NULL) — the brief is a context/handoff package, not a
notification. Mirrors ``research/store.py::write_research_packet_receipt``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator

if TYPE_CHECKING:
    from .models import DailyBriefContext


def write_daily_brief_run(
    context: DailyBriefContext,
    *,
    mode: str = "dry_run",
    db_path: str | None = None,
) -> str:
    """Insert one daily-brief run + its source refs; returns the ``brief_run_id``.

    Local-only, additive, metadata-only. Guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V26 tables exist (idempotent)

    brief_run_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO daily_brief_runs
                (brief_run_id, brief_date, mode, status, project_count, source_ref_count,
                 review_required_count, stale_unknown_count, research_packet_id,
                 evaluation_run_id, review_tier, review_tier_reason_code, degradation_mode,
                 output_path_redacted, output_path_hash, generated_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                brief_run_id,
                context.brief_date,
                mode,
                context.status,
                context.project_count,
                context.source_ref_count,
                context.review_required_count,
                context.stale_unknown_count,
                context.research_packet_id,
                context.review_tier,
                context.review_tier_reason_code,
                context.degradation_mode,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        for ref in context.source_refs:
            conn.execute(
                """
                INSERT INTO daily_brief_source_refs
                    (daily_brief_source_ref_id, brief_run_id, source_family, source_ref,
                     evidence_trail_id, confidence_class, review_required, stale_unknown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    brief_run_id,
                    ref.get("source_family", ""),
                    ref.get("source_ref", ""),
                    ref.get("evidence_trail_id"),
                    ref.get("confidence_class"),
                    1 if ref.get("review_required") in (True, "true", "1", 1) else 0,
                    1 if ref.get("stale_unknown") in (True, "true", "1", 1) else 0,
                ),
            )
    return brief_run_id


def read_latest_daily_brief_runs(
    *, db_path: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent daily-brief run rows (metadata only)."""
    SQLiteMigrator(db_path).apply()  # ensure V26 tables exist (idempotent)
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT brief_run_id, brief_date, mode, status, project_count, source_ref_count,
               review_required_count, stale_unknown_count, research_packet_id, review_tier,
               review_tier_reason_code, degradation_mode, generated_utc
        FROM daily_brief_runs
        ORDER BY generated_utc DESC, brief_run_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
