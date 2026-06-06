"""Phase 08A allowlisted source-family readers (Synthesized Prompt 04).

Each reader returns bounded, redacted `RetrievalItem`s from one allowlisted local
read-model. Readers reuse `ConstructionStore.list_*` where available and otherwise
issue FIXED parameterized SELECTs over hardcoded safe columns. No `*` selects, no
dynamic SQL, no raw bodies/URLs/secrets. Families without a read model return no
items (the broker records a coverage warning).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

from .models import RetrievalItem
from .policy import derive_relationship_state, relationship_state_tier


def _tier(review_required: bool, confidence_class: str | None) -> tuple[int, str]:
    # Recognize both the generic (high/medium/low) and the construction-substrate
    # (deterministic / strong_heuristic / weak_heuristic / model_proposed / stale_or_unresolved)
    # confidence vocabularies. Deterministic is the highest-trust class (tier 1); strong_heuristic is
    # review-recommended (tier 2); everything weaker / unknown stays review-required (tier 3).
    if review_required:
        return 3, "review_required"
    c = (confidence_class or "").lower()
    if c in ("high", "deterministic"):
        return 1, "auto_advisory"
    if c in ("medium", "strong_heuristic"):
        return 2, "review_recommended"
    return 3, "review_required"


def _flags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _conn(db_path: str | None):  # type: ignore[no-untyped-def]
    return get_connection(Path(db_path) if db_path is not None else None)


def read_relationships(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    items: list[RetrievalItem] = []
    for rec in store.list_cross_source_relationships(project_key=project_key, limit=500):
        state = derive_relationship_state(rec)
        # A row flagged review_required is always Tier 3 (mandatory review), overriding
        # the derived state's base tier; never auto-accepted as a conclusion.
        tier = 3 if rec.get("review_required") else relationship_state_tier(state)
        status = (
            "review_required"
            if tier == 3
            else ("review_recommended" if tier == 2 else "auto_advisory")
        )
        items.append(
            RetrievalItem(
                source_family="cross_source_relationships",
                source_ref=str(rec.get("relationship_id")),
                record_type=str(rec.get("relationship_type") or "relationship"),
                record_ref=str(rec.get("relationship_id")),
                project_key=rec.get("project_key"),
                confidence_class=str(rec.get("confidence_class") or "unknown"),
                review_tier=tier,
                review_status=status,
                review_required=tier == 3,
                relationship_state=state,
                evidence_ref=rec.get("evidence_trail_id"),
                content_excerpt_redacted=(
                    f"{rec.get('source_family')}->{rec.get('target_family')} "
                    f"{rec.get('relationship_type')} [{state}]"
                ),
                recency=str(rec.get("relationship_id") or ""),
            )
        )
    return items


def read_evidence_trails(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    items: list[RetrievalItem] = []
    for rec in store.list_source_evidence_trails(project_key=project_key, limit=500):
        review_required = bool(rec.get("review_required"))
        tier, status = _tier(review_required, rec.get("confidence_class"))
        items.append(
            RetrievalItem(
                source_family="phase_07d_source_evidence_trails",
                source_ref=str(rec.get("evidence_trail_id")),
                record_type=str(rec.get("evidence_kind") or "evidence_trail"),
                record_ref=str(rec.get("evidence_trail_id")),
                project_key=rec.get("project_key"),
                confidence_class=str(rec.get("confidence_class") or "unknown"),
                review_tier=tier,
                review_status=status,
                review_required=review_required,
                evidence_ref=rec.get("evidence_trail_id"),
                stale_unknown_flags=_flags(rec.get("stale_unknown_flags_json")),
                content_excerpt_redacted=str(rec.get("evidence_kind") or "evidence_trail"),
                recency=str(rec.get("generated_utc") or ""),
            )
        )
    return items


def read_issue_history(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    items: list[RetrievalItem] = []
    for rec in store.list_project_issue_history_items(project_key=project_key, limit=500):
        review_required = bool(rec.get("review_required"))
        tier, status = _tier(review_required, rec.get("confidence_class"))
        items.append(
            RetrievalItem(
                source_family="project_issue_history_items",
                source_ref=str(rec.get("issue_family_id")),
                record_type=str(rec.get("issue_kind") or "issue"),
                record_ref=str(rec.get("issue_family_id")),
                project_key=rec.get("project_key"),
                confidence_class=str(rec.get("confidence_class") or "unknown"),
                review_tier=tier,
                review_status=status,
                review_required=review_required,
                evidence_ref=rec.get("evidence_trail_id"),
                stale_unknown_flags=_flags(rec.get("stale_unknown_flags_json")),
                content_excerpt_redacted=(
                    f"{rec.get('issue_kind')} status={rec.get('status')} age={rec.get('age_days')}d"
                ),
                recency=str(rec.get("updated_utc") or ""),
            )
        )
    return items


def _read_bounded(
    db_path: str | None,
    *,
    family: str,
    table: str,
    columns: list[str],
    id_col: str,
    type_col: str | None,
    excerpt_col: str | None,
    project_key: str | None,
    where_extra: str = "",
    conn: Any = None,
) -> list[RetrievalItem]:
    # ``conn`` lets a caller (e.g. the Prompt-06 query-tool layer) inject a
    # read-only (PRAGMA query_only) connection so the bounded SELECT runs under an
    # enforced read-only posture; default opens the canonical connection.
    if conn is None:
        conn = _conn(db_path)
    where = "WHERE 1=1"
    params: list[Any] = []
    if project_key is not None and "project_key" in columns:
        where += " AND project_key = ?"
        params.append(project_key)
    where += where_extra
    sql = f"SELECT {', '.join(columns)} FROM {table} {where} ORDER BY {id_col} LIMIT 500"
    items: list[RetrievalItem] = []
    for row in conn.execute(sql, tuple(params)).fetchall():
        rec = dict(row)
        review_required = bool(rec.get("review_required", 0))
        tier, status = _tier(review_required, rec.get("confidence_class"))
        excerpt = str(rec.get(excerpt_col)) if excerpt_col and rec.get(excerpt_col) else family
        items.append(
            RetrievalItem(
                source_family=family,
                source_ref=str(rec.get(id_col)),
                record_type=str(rec.get(type_col) if type_col else family),
                record_ref=str(rec.get(id_col)),
                project_key=rec.get("project_key"),
                confidence_class=str(rec.get("confidence_class") or "unknown"),
                review_tier=tier,
                review_status=status,
                review_required=review_required,
                evidence_ref=rec.get("evidence_trail_id"),
                content_excerpt_redacted=excerpt,
                recency=str(rec.get("created_utc") or rec.get("updated_utc") or ""),
            )
        )
    return items


def read_risk_digest(
    store: ConstructionStore, db_path: str | None, project_key: str | None, conn: Any = None
) -> list[RetrievalItem]:
    return _read_bounded(
        db_path,
        family="project_risk_digest_items",
        table="project_risk_digest_items",
        columns=[
            "risk_digest_id",
            "project_key",
            "risk_indicator_type",
            "summary_redacted",
            "evidence_trail_id",
            "confidence_class",
            "review_required",
            "created_utc",
        ],
        id_col="risk_digest_id",
        type_col="risk_indicator_type",
        excerpt_col="summary_redacted",
        project_key=project_key,
        conn=conn,
    )


def read_aging_exposure(
    store: ConstructionStore, db_path: str | None, project_key: str | None, conn: Any = None
) -> list[RetrievalItem]:
    return _read_bounded(
        db_path,
        family="aging_exposure_report_items",
        table="aging_exposure_report_items",
        columns=[
            "aging_item_id",
            "project_key",
            "record_family",
            "status",
            "age_days",
            "threshold_band",
            "evidence_trail_id",
            "confidence_class",
            "review_required",
            "created_utc",
        ],
        id_col="aging_item_id",
        type_col="record_family",
        excerpt_col="threshold_band",
        project_key=project_key,
        conn=conn,
    )


def read_approved_obsidian(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    from ..obsidian_index import list_approved_obsidian_index_entries

    items: list[RetrievalItem] = []
    for rec in list_approved_obsidian_index_entries(db_path=db_path, limit=500):
        if project_key is not None and rec.get("project_key") not in (None, project_key):
            continue
        meta = rec.get("meta") or {}
        tier = int(meta.get("review_tier", 1))
        status = (
            "review_required"
            if tier == 3
            else ("review_recommended" if tier == 2 else "auto_advisory")
        )
        items.append(
            RetrievalItem(
                source_family="approved_obsidian_generated_outputs",
                source_ref=str(rec.get("note_path_hash")),
                record_type=str(rec.get("source_type") or "obsidian_note"),
                record_ref=str(rec.get("content_hash")),
                project_key=rec.get("project_key"),
                confidence_class=str(rec.get("confidence_class") or "high"),
                review_tier=tier,
                review_status=str(rec.get("review_status") or status),
                review_required=tier == 3,
                content_excerpt_redacted=str(
                    rec.get("heading_redacted") or rec.get("section_marker") or ""
                ),
                recency=str(rec.get("modified_utc") or ""),
            )
        )
    return items


def read_accepted_memory(
    store: ConstructionStore, db_path: str | None, project_key: str | None, conn: Any = None
) -> list[RetrievalItem]:
    return _read_bounded(
        db_path,
        family="accepted_long_term_memory",
        table="long_term_memory_items",
        columns=[
            "memory_id",
            "project_key",
            "memory_type",
            "statement_redacted",
            "confidence_class",
            "review_status",
            "created_utc",
        ],
        id_col="memory_id",
        type_col="memory_type",
        excerpt_col="statement_redacted",
        project_key=project_key,
        where_extra=" AND review_status = 'accepted'",
        conn=conn,
    )


def _table_exists(conn: Any, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def read_generated_outputs(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    """Accepted research packets + applied, source-linked daily briefs (redacted, source-linked).

    Mirrors the manifest's generated-outputs candidate logic (``source_manifest._read_generated``) but
    yields ``RetrievalItem``s for the deterministic broker. No raw content: packet excerpts come from
    ``summary_redacted`` and brief excerpts are a bounded label only.
    """
    conn = _conn(db_path)
    items: list[RetrievalItem] = []
    if _table_exists(conn, "second_brain_research_packets"):
        clause = " AND project_key = ?" if project_key is not None else ""
        params: list[Any] = ["accepted"]
        if project_key is not None:
            params.append(project_key)
        rows = conn.execute(
            "SELECT packet_id, project_key, confidence_class, review_tier, review_status, "
            "summary_redacted, created_utc FROM second_brain_research_packets "
            "WHERE review_status = ?" + clause + " ORDER BY packet_id LIMIT 500",
            tuple(params),
        ).fetchall()
        for rec in (dict(r) for r in rows):
            tier = int(rec.get("review_tier") or 1)
            review_required = tier >= 3
            items.append(
                RetrievalItem(
                    source_family="generated_outputs",
                    source_ref=str(rec.get("packet_id")),
                    record_type="research_packet",
                    record_ref=str(rec.get("packet_id")),
                    project_key=rec.get("project_key"),
                    confidence_class=str(rec.get("confidence_class") or "unknown"),
                    review_tier=tier,
                    review_status=str(rec.get("review_status") or "accepted"),
                    review_required=review_required,
                    content_excerpt_redacted=str(rec.get("summary_redacted") or "research_packet"),
                    recency=str(rec.get("created_utc") or ""),
                )
            )
    # daily_brief_runs has no project_key column; only enumerate when unscoped.
    if project_key is None and _table_exists(conn, "daily_brief_runs"):
        rows = conn.execute(
            "SELECT brief_run_id, brief_date, review_tier, status FROM daily_brief_runs "
            "WHERE mode = 'apply' AND status != 'blocked' AND output_path_hash IS NOT NULL "
            "AND source_ref_count > 0 ORDER BY generated_utc DESC, brief_run_id DESC LIMIT 500"
        ).fetchall()
        for rec in (dict(r) for r in rows):
            tier = int(rec.get("review_tier") or 1)
            items.append(
                RetrievalItem(
                    source_family="generated_outputs",
                    source_ref=str(rec.get("brief_run_id")),
                    record_type="daily_brief",
                    record_ref=str(rec.get("brief_run_id")),
                    confidence_class="high",
                    review_tier=tier,
                    review_status="auto_advisory",
                    review_required=tier >= 3,
                    content_excerpt_redacted=f"daily brief {rec.get('brief_date') or ''}".strip(),
                    recency=str(rec.get("brief_date") or ""),
                )
            )
    return items


def read_meeting_prep_brief_sections(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    """Meeting-prep brief sections (V25). Redacted, source-linked; ``section_redacted`` excerpt only.

    The table has no ``project_key`` column, so the (rare) project-scoped path returns no items rather
    than leaking cross-project rows.
    """
    if project_key is not None:
        return []
    items: list[RetrievalItem] = []
    for rec in store.list_meeting_prep_brief_sections(limit=500):
        review_required = bool(rec.get("review_required"))
        tier, status = _tier(review_required, rec.get("confidence_class"))
        items.append(
            RetrievalItem(
                source_family="meeting_prep_brief_sections",
                source_ref=str(rec.get("section_id")),
                record_type=str(rec.get("section_kind") or "section"),
                record_ref=str(rec.get("section_id")),
                confidence_class=str(rec.get("confidence_class") or "unknown"),
                review_tier=tier,
                review_status=status,
                review_required=review_required,
                evidence_ref=rec.get("evidence_trail_id"),
                stale_unknown_flags=_flags(rec.get("stale_unknown_flags_json")),
                content_excerpt_redacted=str(rec.get("section_redacted") or "section"),
                recency=str(rec.get("generated_utc") or ""),
            )
        )
    return items


def read_review_controlled_correspondence_context(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    """Review-controlled correspondence context — bounded, redacted email-thread summaries.

    Reads the redacted ``email_thread_summaries`` read model directly (one bounded query, the same
    single-connection pattern as the other deterministic readers) rather than the heavy Phase 07D
    relationship-join projection — keeping the broker hot path light. Each thread becomes one item:
    ``source_ref`` is the thread key, the excerpt is the bounded ``summary_redacted`` (never a raw
    body / subject / link), and the tier is floored at 2 (advisory, never auto-tier-1) — review-required
    threads stay tier 3 and are dropped by the read-model loader's eligibility filter, so they are never
    vector-indexed.
    """
    items: list[RetrievalItem] = []
    for rec in store.list_email_thread_summaries(project_key=project_key, limit=500):
        review_required = bool(rec.get("review_required"))
        tier = 3 if review_required else 2
        items.append(
            RetrievalItem(
                source_family="review_controlled_correspondence_context",
                source_ref=str(rec.get("thread_key")),
                record_type="correspondence_thread",
                record_ref=str(rec.get("thread_key")),
                project_key=rec.get("project_key"),
                confidence_class="unknown",
                review_tier=tier,
                review_status="review_required" if review_required else "review_recommended",
                review_required=review_required,
                content_excerpt_redacted=str(rec.get("summary_redacted") or "correspondence"),
                recency=str(rec.get("last_message_datetime") or ""),
            )
        )
    return items


# Families with a registered reader. Allowlisted families NOT here yield no items;
# the broker records a coverage warning (graceful degradation, never fabricate).
READER_REGISTRY: dict[
    str, Callable[[ConstructionStore, str | None, str | None], list[RetrievalItem]]
] = {
    "cross_source_relationships": read_relationships,
    "phase_07d_source_evidence_trails": read_evidence_trails,
    "project_issue_history_items": read_issue_history,
    "project_risk_digest_items": read_risk_digest,
    "aging_exposure_report_items": read_aging_exposure,
    "accepted_long_term_memory": read_accepted_memory,
    "approved_obsidian_generated_outputs": read_approved_obsidian,
    "generated_outputs": read_generated_outputs,
    "meeting_prep_brief_sections": read_meeting_prep_brief_sections,
    "review_controlled_correspondence_context": read_review_controlled_correspondence_context,
}
