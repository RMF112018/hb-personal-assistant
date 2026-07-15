"""Phase 08A daily-brief run store (Prompt 11).

Writes a metadata-only daily-brief run into the existing V26 ``daily_brief_runs`` table
(+ ``daily_brief_source_refs``). Both tables enforce ``CHECK(col = 0)`` no-raw /
no-writeback guard columns; this writer leaves them all at 0 and persists only counts,
classes, the redacted research-packet link, and source-ref identifiers. No output file is
rendered (``output_path_*`` stay NULL) — the brief is a context/handoff package, not a
notification. Mirrors ``research/store.py::write_research_packet_receipt``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import ensure_schema_ready

if TYPE_CHECKING:
    from .models import (
        DailyBriefContext,
        DeliveryHandoffPayload,
        HandoffLine,
        LaunchdSchedulePreview,
    )


def write_daily_brief_run(
    context: DailyBriefContext,
    *,
    mode: str = "dry_run",
    db_path: str | None = None,
    evaluation_run_id: str | None = None,
    output_path_redacted: str | None = None,
    output_path_hash: str | None = None,
) -> str:
    """Insert one daily-brief run + its source refs; returns the ``brief_run_id``.

    Local-only, additive, metadata-only. Guard columns stay at 0 via DB CHECKs.
    ``evaluation_run_id`` links the Output Evaluation Agent (A05) row; the
    ``output_path_*`` pair is recorded only when an approved local output was written.
    """
    ensure_schema_ready(db_path)  # ensure V26 tables exist (idempotent)

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                evaluation_run_id,
                context.review_tier,
                context.review_tier_reason_code,
                context.degradation_mode,
                output_path_redacted,
                output_path_hash,
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
    ensure_schema_ready(db_path)  # ensure V26 tables exist (idempotent)
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


def write_daily_brief_handoff_lines(
    sections: dict[str, list[HandoffLine]],
    *,
    brief_run_id: str,
    db_path: str | None = None,
) -> int:
    """Persist the structured delivery-handoff lines for a brief run; returns rows written.

    Phase 08B durable handoff recovery (V27): stores section + ordered position + redacted
    title + review tier + safe source-ref pairs per line so the full handoff can be
    reconstructed after process exit. Metadata-only — each line's ``source_refs`` is run
    through the forbidden-field guard before serialization, and the row's no-raw /
    no-writeback CHECK guard columns stay at 0. Lines are written in ``HANDOFF_SECTIONS``
    order; ``brief_run_id`` must reference an existing ``daily_brief_runs`` row.
    """
    from .models import HANDOFF_SECTIONS, _reject_forbidden_refs

    ensure_schema_ready(db_path)  # ensure V27 table exists (idempotent)

    conn = get_connection(Path(db_path) if db_path is not None else None)
    written = 0
    with transaction(conn):
        for section in HANDOFF_SECTIONS:
            for line_index, line in enumerate(sections.get(section, [])):
                safe_refs = _reject_forbidden_refs(list(line.source_refs))
                conn.execute(
                    """
                    INSERT INTO daily_brief_handoff_lines
                        (line_id, brief_run_id, section, line_index, title_redacted,
                         review_tier, source_refs_json, generated_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        brief_run_id,
                        section,
                        line_index,
                        line.title_redacted,
                        line.review_tier,
                        json.dumps(safe_refs, sort_keys=True),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                written += 1
    return written


def read_daily_brief_handoff(
    brief_run_id: str, *, db_path: str | None = None
) -> DeliveryHandoffPayload | None:
    """Reconstruct the full, safe delivery-handoff payload for a persisted brief run.

    Reads ``daily_brief_runs`` + ``daily_brief_handoff_lines`` + ``daily_brief_source_refs``
    and rebuilds a :class:`DeliveryHandoffPayload` (sections grouped + ordered by
    ``section, line_index``; derived data-only notification summary and HTML render-data with
    ``rendered=False``). Returns ``None`` when ``brief_run_id`` is unknown. Deterministic,
    metadata-only — no raw content; nothing is written.
    """
    from .models import (
        HANDOFF_SECTIONS,
        DeliveryHandoffPayload,
        HandoffLine,
        HtmlRenderingData,
        NotificationSummary,
    )

    ensure_schema_ready(db_path)  # ensure V27 table exists (idempotent)
    conn = get_connection(Path(db_path) if db_path is not None else None)

    run = conn.execute(
        """
        SELECT brief_run_id, brief_date, status, project_count, review_required_count,
               stale_unknown_count, evaluation_run_id, review_tier, degradation_mode
        FROM daily_brief_runs WHERE brief_run_id = ?
        """,
        (brief_run_id,),
    ).fetchone()
    if run is None:
        return None

    # Pre-seed all canonical sections (empty lists) so the reconstructed shape mirrors the
    # in-memory handoff faithfully, then fill ordered lines.
    sections: dict[str, list[HandoffLine]] = {name: [] for name in HANDOFF_SECTIONS}
    for row in conn.execute(
        """
        SELECT section, title_redacted, review_tier, source_refs_json
        FROM daily_brief_handoff_lines
        WHERE brief_run_id = ?
        ORDER BY section, line_index
        """,
        (brief_run_id,),
    ).fetchall():
        sections.setdefault(row["section"], []).append(
            HandoffLine(
                title_redacted=row["title_redacted"],
                review_tier=row["review_tier"] if row["review_tier"] is not None else 3,
                source_refs=json.loads(row["source_refs_json"] or "[]"),
            )
        )

    source_refs: list[dict[str, str]] = []
    for row in conn.execute(
        """
        SELECT source_family, source_ref, evidence_trail_id, confidence_class
        FROM daily_brief_source_refs WHERE brief_run_id = ?
        ORDER BY rowid
        """,
        (brief_run_id,),
    ).fetchall():
        ref = {"source_family": row["source_family"], "source_ref": row["source_ref"]}
        if row["evidence_trail_id"] is not None:
            ref["evidence_trail_id"] = row["evidence_trail_id"]
        if row["confidence_class"] is not None:
            ref["confidence_class"] = row["confidence_class"]
        source_refs.append(ref)

    title = f"Daily Brief {run['brief_date']}"
    eligible = run["status"] != "blocked"
    notification = NotificationSummary(
        title_redacted=title,
        attention_count=len(sections.get("priority_actions", [])),
        review_required_count=run["review_required_count"],
        warning_count=len(sections.get("waiting_on", [])),
        project_count=run["project_count"],
        eligible=eligible,
    )
    html = HtmlRenderingData(title_redacted=title, sections=sections, source_refs=source_refs)
    return DeliveryHandoffPayload(
        brief_run_id=run["brief_run_id"],
        brief_date=run["brief_date"],
        evaluation_run_id=run["evaluation_run_id"],
        eligible_for_delivery=eligible,
        review_tier=run["review_tier"] if run["review_tier"] is not None else 3,
        degradation_mode=run["degradation_mode"] or "blocked",
        sections=sections,
        source_refs=source_refs,
        notification_summary=notification,
        html_rendering=html,
    )


def write_launchd_schedule_preview(
    preview: LaunchdSchedulePreview,
    *,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only launchd schedule preview; returns the ``preview_id``.

    Dry-run only by construction (the table enforces ``mode = 'dry_run'``). No plist is
    written and ``launchctl`` is never invoked. Guard column stays at 0 via the DB CHECK.
    """
    ensure_schema_ready(db_path)  # ensure V26 table exists (idempotent)

    preview_id = uuid.uuid4().hex
    schedule_json = json.dumps(
        {
            "hour": preview.hour,
            "minute": preview.minute,
            "day_offset": preview.day_offset,
            "command_mode": preview.command_mode,
            "program_arguments": preview.program_arguments_redacted,
        },
        sort_keys=True,
    )

    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO launchd_schedule_previews
                (launchd_preview_id, mode, label, schedule_json, plist_path_redacted,
                 log_dir_redacted, generated_utc)
            VALUES (?, 'dry_run', ?, ?, ?, ?, ?)
            """,
            (
                preview_id,
                preview.label,
                schedule_json,
                preview.plist_path_redacted,
                preview.log_dir_redacted,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return preview_id


def read_latest_launchd_schedule_previews(
    *, db_path: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent launchd schedule-preview rows (metadata only)."""
    ensure_schema_ready(db_path)  # ensure V26 table exists (idempotent)
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT launchd_preview_id, mode, label, schedule_json, plist_path_redacted,
               log_dir_redacted, generated_utc, external_writeback_performed
        FROM launchd_schedule_previews
        ORDER BY generated_utc DESC, launchd_preview_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
