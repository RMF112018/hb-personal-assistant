"""Phase 08A research-packet receipt store (Prompt 07).

Writes a metadata-only research-packet row into the V26 ``second_brain_research_packets``
table (1:1 with `ResearchPacket`). The table enforces ten ``CHECK(col = 0)`` no-raw /
no-writeback guard columns; this writer leaves them all at 0 and persists only counts,
classes, redacted summary, and coverage-warning codes. Mirrors
``second_brain/store.py::write_config_receipt``.
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
    from .models import ResearchPacket


def write_research_packet_receipt(
    *,
    packet: ResearchPacket,
    mode: str = "dry_run",
    db_path: str | None = None,
) -> str:
    """Insert one research-packet row; returns the generated ``packet_id``.

    Local-only, additive, metadata-only. Guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V26 table exists (idempotent)

    packet_id = packet.packet_id or uuid.uuid4().hex
    coverage_warnings_json = json.dumps(packet.coverage_warnings, sort_keys=True)

    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_research_packets
                (packet_id, mode, topic_hash, project_key, retrieval_receipt_id,
                 source_ref_count, review_required_count, stale_unknown_count, conflict_count,
                 coverage_warnings_json, context_quality_class, degradation_mode,
                 confidence_class, review_tier, review_tier_reason_code, review_status,
                 advisory_classification, summary_redacted, status, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                packet_id,
                mode,
                packet.topic_hash,
                packet.project_key,
                packet.retrieval_receipt_id,
                packet.source_ref_count,
                packet.review_required_count,
                packet.stale_unknown_count,
                packet.conflict_count,
                coverage_warnings_json,
                packet.context_quality_class,
                packet.degradation_mode,
                packet.confidence_class,
                packet.review_tier,
                packet.review_tier_reason_code,
                packet.review_status,
                packet.advisory_classification,
                packet.summary_redacted,
                packet.status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return packet_id


def read_latest_research_packets(
    *, db_path: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent research-packet rows (metadata only)."""
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT packet_id, mode, topic_hash, project_key, retrieval_receipt_id,
               source_ref_count, review_required_count, stale_unknown_count, conflict_count,
               context_quality_class, degradation_mode, confidence_class, review_tier,
               review_status, status, created_utc
        FROM second_brain_research_packets
        ORDER BY created_utc DESC, packet_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
