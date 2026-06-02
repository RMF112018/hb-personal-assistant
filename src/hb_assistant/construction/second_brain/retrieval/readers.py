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
    if review_required:
        return 3, "review_required"
    c = (confidence_class or "").lower()
    if c == "high":
        return 1, "auto_advisory"
    if c == "medium":
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
        status = "review_required" if tier == 3 else ("review_recommended" if tier == 2 else "auto_advisory")
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
) -> list[RetrievalItem]:
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
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    return _read_bounded(
        db_path,
        family="project_risk_digest_items",
        table="project_risk_digest_items",
        columns=[
            "risk_digest_id", "project_key", "risk_indicator_type", "summary_redacted",
            "evidence_trail_id", "confidence_class", "review_required", "created_utc",
        ],
        id_col="risk_digest_id",
        type_col="risk_indicator_type",
        excerpt_col="summary_redacted",
        project_key=project_key,
    )


def read_aging_exposure(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    return _read_bounded(
        db_path,
        family="aging_exposure_report_items",
        table="aging_exposure_report_items",
        columns=[
            "aging_item_id", "project_key", "record_family", "status", "age_days",
            "threshold_band", "evidence_trail_id", "confidence_class", "review_required",
            "created_utc",
        ],
        id_col="aging_item_id",
        type_col="record_family",
        excerpt_col="threshold_band",
        project_key=project_key,
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
        status = "review_required" if tier == 3 else ("review_recommended" if tier == 2 else "auto_advisory")
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
                content_excerpt_redacted=str(rec.get("heading_redacted") or rec.get("section_marker") or ""),
                recency=str(rec.get("modified_utc") or ""),
            )
        )
    return items


def read_accepted_memory(
    store: ConstructionStore, db_path: str | None, project_key: str | None
) -> list[RetrievalItem]:
    return _read_bounded(
        db_path,
        family="accepted_long_term_memory",
        table="long_term_memory_items",
        columns=[
            "memory_id", "project_key", "memory_type", "statement_redacted",
            "confidence_class", "review_status", "created_utc",
        ],
        id_col="memory_id",
        type_col="memory_type",
        excerpt_col="statement_redacted",
        project_key=project_key,
        where_extra=" AND review_status = 'accepted'",
    )


# Families with a registered reader. Allowlisted families NOT here yield no items;
# the broker records a coverage warning (graceful degradation, never fabricate).
READER_REGISTRY: dict[str, Callable[[ConstructionStore, str | None, str | None], list[RetrievalItem]]] = {
    "cross_source_relationships": read_relationships,
    "phase_07d_source_evidence_trails": read_evidence_trails,
    "project_issue_history_items": read_issue_history,
    "project_risk_digest_items": read_risk_digest,
    "aging_exposure_report_items": read_aging_exposure,
    "accepted_long_term_memory": read_accepted_memory,
    "approved_obsidian_generated_outputs": read_approved_obsidian,
}
