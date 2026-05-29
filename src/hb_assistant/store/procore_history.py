"""Phase 04B history-recording repository + diff engine.

Turns each current-state Procore upsert into historical memory: per-record
**snapshots**, field-level **change events**, and **timeline events**. The
existing ``procore_live_records`` latest-state table is unaffected — this module
writes alongside it into the V7 history tables.

Inputs are always the already-redacted canonical-field dicts produced by the
normalizers (free text -> ``*_summary`` hash blocks, people -> hashed entities),
so diffing them never surfaces raw PII. As a second line of defence
``_value_repr`` keeps only short scalars verbatim and reduces dicts / lists /
long strings to a hash. All snapshot / change / timeline ids are deterministic
and every insert is ``INSERT OR IGNORE``, so re-syncing identical data records
no duplicate history (idempotent).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .connection import get_connection, transaction

_MISSING = object()
_MAX_SCALAR_LEN = 120

# Stable-id keys used to diff lists of dicts by identity rather than position.
_STABLE_KEYS = ("id", "hash_prefix", "to_ref", "custom_field_key", "response_option_id")

# Status tokens used to detect closed / reopened transitions (case-insensitive).
_CLOSED_TOKENS = ("closed", "complete", "completed", "approved", "resolved", "done", "accepted")
_OPEN_TOKENS = ("open", "pending", "draft", "in_progress", "in progress", "reopened", "not_started")

# Change categories that warrant an assistant-ready timeline event.
_SIGNIFICANT = {
    "record_created",
    "status_changed",
    "closed",
    "reopened",
    "became_overdue",
    "due_date_changed",
    "assignee_changed",
    "ball_in_court_changed",
    "response_added",
    "attachment_added",
    "cost_impact_changed",
    "schedule_impact_changed",
    "inspection_item_response_changed",
    "inspection_item_became_unanswered",
    "inspection_item_became_deficient",
}
_HIGH = {
    "closed",
    "reopened",
    "became_overdue",
    "status_changed",
    "cost_impact_changed",
    "schedule_impact_changed",
    "inspection_item_became_deficient",
}


def _open(db_path: Optional[Path]) -> sqlite3.Connection:
    return get_connection(db_path)


def _record_key(
    project_key: str, endpoint_id: str, parent_procore_id: Optional[str], procore_record_id: str
) -> str:
    return "|".join([project_key, endpoint_id, parent_procore_id or "", str(procore_record_id)])


def _canonical_json(normalized_fields: Mapping[str, Any]) -> str:
    return json.dumps(dict(normalized_fields), default=str, sort_keys=True)


def compute_canonical_hash(normalized_fields: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical (sorted-key) JSON — matches the upsert serialization."""
    return hashlib.sha256(_canonical_json(normalized_fields).encode("utf-8")).hexdigest()


def _short_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Diff engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeEvent:
    field_path: str
    change_type: str  # "added" | "removed" | "modified"
    change_category: str
    old_value_redacted: Optional[str]
    new_value_redacted: Optional[str]
    old_value_hash: Optional[str]
    new_value_hash: Optional[str]
    importance: str  # "low" | "medium" | "high"
    review_required: bool
    significant: bool


def _value_repr(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(redacted, hash)``. Short scalars are kept verbatim; dicts /
    lists / long strings carry a hash only (no raw value)."""
    if value is _MISSING or value is None:
        return None, None
    h = hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    if isinstance(value, bool):
        return str(value), h
    if isinstance(value, (int, float)):
        return str(value), h
    if isinstance(value, str):
        return (value if len(value) <= _MAX_SCALAR_LEN else None), h
    return None, h


def _leaf(field_path: str) -> str:
    seg = field_path.replace("]", "").split(".")[-1]
    return seg.split("[")[0]


def _has_token(value: Any, tokens: Tuple[str, ...]) -> bool:
    if value is _MISSING or value is None:
        return False
    s = str(value).lower()
    return any(tok in s for tok in tokens)


def _classify(field_path: str, old: Any, new: Any, change_type: str) -> Tuple[str, str, bool]:
    """Return ``(change_category, importance, significant)``."""
    p = field_path.lower()
    leaf = _leaf(p)

    def out(cat: str, imp: str) -> Tuple[str, str, bool]:
        return cat, imp, cat in _SIGNIFICANT

    if leaf == "status":
        new_closed, old_closed = _has_token(new, _CLOSED_TOKENS), _has_token(old, _CLOSED_TOKENS)
        if new_closed and not old_closed:
            return out("closed", "high")
        if old_closed and not new_closed:
            return out("reopened", "high")
        return out("status_changed", "high")
    if leaf == "overdue" and bool(new) and old in (_MISSING, None, 0, False):
        return out("became_overdue", "high")
    if leaf in ("due_date", "due_at", "compliance_due"):
        return out("due_date_changed", "medium")
    if "ball_in_court" in p:
        return out("ball_in_court_changed", "medium")
    if "assignee" in p:
        return out("assignee_changed", "medium")
    if leaf in ("responses_count", "replies_count") and isinstance(old, int) and isinstance(new, int) and new > old:
        return out("response_added", "medium")
    if change_type == "added" and any(seg in p for seg in (".responses", ".replies", ".topics")):
        return out("response_added", "medium")
    if "attachment" in p:
        if change_type == "added":
            return out("attachment_added", "low")
        if leaf in ("count", "attachments_count") and isinstance(old, int) and isinstance(new, int) and new > old:
            return out("attachment_added", "low")
    if "cost_impact" in p:
        return out("cost_impact_changed", "high")
    if "schedule_impact" in p or "schedule_risk" in p:
        return out("schedule_impact_changed", "high")
    if leaf in ("responded_with", "response_status"):
        return out("inspection_item_response_changed", "medium")
    if leaf == "is_unanswered" and bool(new):
        return out("inspection_item_became_unanswered", "medium")
    if leaf == "is_deficient" and bool(new):
        return out("inspection_item_became_deficient", "high")
    if leaf == "priority":
        return out("priority_changed", "medium")
    if leaf.endswith("_summary") or leaf in (
        "body", "description", "comment", "note", "details", "minutes", "narrative",
        "conclusion", "safety_notice", "contents",
    ):
        return out("text_changed", "low")
    return out("field_changed", "low")


def _make_event(field_path: str, old: Any, new: Any, change_type: str) -> ChangeEvent:
    category, importance, significant = _classify(field_path, old, new, change_type)
    old_red, old_hash = _value_repr(old)
    new_red, new_hash = _value_repr(new)
    return ChangeEvent(
        field_path=field_path,
        change_type=change_type,
        change_category=category,
        old_value_redacted=old_red,
        new_value_redacted=new_red,
        old_value_hash=old_hash,
        new_value_hash=new_hash,
        importance=importance,
        review_required=importance == "high",
        significant=significant,
    )


def _stable_key_of(elem: Any) -> Optional[str]:
    if not isinstance(elem, dict):
        return None
    for key in _STABLE_KEYS:
        if elem.get(key) is not None:
            return f"{key}={elem[key]}"
    return None


def _diff_list(path: str, old: list, new: list, events: List[ChangeEvent]) -> None:
    old_keyed = {k: e for e in old if (k := _stable_key_of(e)) is not None}
    new_keyed = {k: e for e in new if (k := _stable_key_of(e)) is not None}
    keyable = len(old_keyed) == len(old) and len(new_keyed) == len(new) and (old or new)
    if keyable:
        for k in new_keyed.keys() - old_keyed.keys():
            events.append(_make_event(f"{path}[{k}]", _MISSING, new_keyed[k], "added"))
        for k in old_keyed.keys() - new_keyed.keys():
            events.append(_make_event(f"{path}[{k}]", old_keyed[k], _MISSING, "removed"))
        for k in old_keyed.keys() & new_keyed.keys():
            _diff_value(f"{path}[{k}]", old_keyed[k], new_keyed[k], events)
        return
    if old != new:
        events.append(_make_event(path, old, new, "modified"))


def _diff_value(path: str, old: Any, new: Any, events: List[ChangeEvent]) -> None:
    if old is _MISSING and new is not _MISSING:
        events.append(_make_event(path, _MISSING, new, "added"))
        return
    if new is _MISSING and old is not _MISSING:
        events.append(_make_event(path, old, _MISSING, "removed"))
        return
    # ``*_summary`` blocks are hash-only representations of redacted free text —
    # treat them as atomic values (a single text_changed event) rather than
    # recursing into their {type,length,hash_prefix} internals.
    if _leaf(path).endswith("_summary"):
        if old != new:
            events.append(_make_event(path, old, new, "modified"))
        return
    if isinstance(old, dict) and isinstance(new, dict):
        _diff_node(path, old, new, events)
    elif isinstance(old, list) and isinstance(new, list):
        _diff_list(path, old, new, events)
    elif old != new:
        events.append(_make_event(path, old, new, "modified"))


def _diff_node(prefix: str, old: Mapping[str, Any], new: Mapping[str, Any], events: List[ChangeEvent]) -> None:
    for key in sorted(set(old) | set(new)):
        child = f"{prefix}.{key}" if prefix else key
        _diff_value(child, old.get(key, _MISSING), new.get(key, _MISSING), events)


def diff_canonical_records(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> List[ChangeEvent]:
    """Field-level diff of two already-redacted canonical-field dicts."""
    events: List[ChangeEvent] = []
    _diff_node("", previous or {}, current or {}, events)
    return events


# ---------------------------------------------------------------------------
# Recorders
# ---------------------------------------------------------------------------


def record_procore_snapshot_if_changed(
    *,
    project_key: str,
    endpoint_id: str,
    parent_procore_id: Optional[str],
    procore_record_id: str,
    normalized_fields: Mapping[str, Any],
    sync_run_id: Optional[str],
    observed_at_utc: str,
    source_updated_at: Optional[str] = None,
    normalizer_version: Optional[str] = None,
    canonical_hash: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Insert a snapshot iff the canonical hash differs from the current state.

    Returns ``{changed, snapshot_id, previous_canonical, is_new, prev_snapshot_id,
    record_key, canonical_hash}``.
    """
    rk = _record_key(project_key, endpoint_id, parent_procore_id, procore_record_id)
    canonical_hash = canonical_hash or compute_canonical_hash(normalized_fields)
    conn = _open(db_path)
    row = conn.execute(
        "SELECT current_canonical_hash, last_snapshot_id FROM procore_live_record_state_index WHERE record_key = ?",
        (rk,),
    ).fetchone()
    prev_hash = row["current_canonical_hash"] if row else None
    prev_snapshot_id = row["last_snapshot_id"] if row else None

    if prev_hash == canonical_hash:
        return {
            "changed": False,
            "snapshot_id": prev_snapshot_id,
            "previous_canonical": None,
            "is_new": False,
            "prev_snapshot_id": prev_snapshot_id,
            "record_key": rk,
            "canonical_hash": canonical_hash,
        }

    previous_canonical: Dict[str, Any] = {}
    if prev_snapshot_id:
        prow = conn.execute(
            "SELECT canonical_json_redacted FROM procore_live_record_snapshots WHERE snapshot_id = ?",
            (prev_snapshot_id,),
        ).fetchone()
        if prow and prow["canonical_json_redacted"]:
            previous_canonical = json.loads(prow["canonical_json_redacted"])

    is_new = prev_hash is None
    snapshot_id = _short_hash(rk, canonical_hash)
    with transaction(conn):
        conn.execute(
            """
            INSERT OR IGNORE INTO procore_live_record_snapshots (
              snapshot_id, record_key, project_key, endpoint_id, parent_procore_id,
              procore_record_id, sync_run_id, observed_at_utc, source_updated_at_utc,
              canonical_hash, canonical_json_redacted, changed_from_previous,
              normalizer_version, raw_body_persisted, redaction_applied
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
            """,
            (
                snapshot_id,
                rk,
                project_key,
                endpoint_id,
                parent_procore_id or "",
                str(procore_record_id),
                sync_run_id,
                observed_at_utc,
                source_updated_at,
                canonical_hash,
                _canonical_json(normalized_fields),
                0 if is_new else 1,
                normalizer_version,
            ),
        )
    return {
        "changed": True,
        "snapshot_id": snapshot_id,
        "previous_canonical": previous_canonical,
        "is_new": is_new,
        "prev_snapshot_id": prev_snapshot_id,
        "record_key": rk,
        "canonical_hash": canonical_hash,
    }


def record_procore_change_events(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    parent_procore_id: Optional[str],
    procore_record_id: str,
    sync_run_id: Optional[str],
    from_snapshot_id: Optional[str],
    to_snapshot_id: Optional[str],
    detected_at_utc: str,
    source_updated_at: Optional[str],
    events: List[ChangeEvent],
    db_path: Optional[Path] = None,
) -> int:
    """Persist field-level change events (deterministic ids; idempotent)."""
    if not events:
        return 0
    conn = _open(db_path)
    written = 0
    with transaction(conn):
        for ev in events:
            change_event_id = _short_hash(
                record_key, to_snapshot_id or "", ev.field_path, ev.change_category
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO procore_live_record_change_events (
                  change_event_id, record_key, project_key, endpoint_id, parent_procore_id,
                  procore_record_id, sync_run_id, from_snapshot_id, to_snapshot_id,
                  detected_at_utc, source_updated_at_utc, field_path,
                  old_value_redacted, new_value_redacted, old_value_hash, new_value_hash,
                  change_type, change_category, importance, review_required, raw_body_persisted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    change_event_id,
                    record_key,
                    project_key,
                    endpoint_id,
                    parent_procore_id or "",
                    str(procore_record_id),
                    sync_run_id,
                    from_snapshot_id,
                    to_snapshot_id,
                    detected_at_utc,
                    source_updated_at,
                    ev.field_path,
                    ev.old_value_redacted,
                    ev.new_value_redacted,
                    ev.old_value_hash,
                    ev.new_value_hash,
                    ev.change_type,
                    ev.change_category,
                    ev.importance,
                    1 if ev.review_required else 0,
                ),
            )
            written += 1
    return written


def record_procore_timeline_events(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    parent_procore_id: Optional[str],
    procore_record_id: str,
    snapshot_id: Optional[str],
    event_time_utc: str,
    events: List[ChangeEvent],
    db_path: Optional[Path] = None,
) -> int:
    """Persist assistant-ready timeline events for significant changes.

    ``summary_redacted`` carries only the category + canonical key path (never
    raw text)."""
    significant = [ev for ev in events if ev.significant]
    if not significant:
        return 0
    conn = _open(db_path)
    written = 0
    with transaction(conn):
        for ev in significant:
            source_change_event_id = _short_hash(
                record_key, snapshot_id or "", ev.field_path, ev.change_category
            )
            timeline_event_id = _short_hash("timeline", source_change_event_id)
            summary = (
                "record created"
                if ev.change_category == "record_created"
                else f"{ev.change_category} ({ev.field_path})"
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO procore_record_timeline_events (
                  timeline_event_id, record_key, project_key, endpoint_id, parent_procore_id,
                  procore_record_id, source_change_event_id, source_snapshot_id, event_type,
                  event_time_utc, summary_redacted, importance, raw_body_persisted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    timeline_event_id,
                    record_key,
                    project_key,
                    endpoint_id,
                    parent_procore_id or "",
                    str(procore_record_id),
                    source_change_event_id,
                    snapshot_id,
                    ev.change_category,
                    event_time_utc,
                    summary,
                    ev.importance,
                ),
            )
            written += 1
    return written


def record_procore_current_state(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    parent_procore_id: Optional[str],
    procore_record_id: str,
    canonical_hash: str,
    snapshot_id: Optional[str],
    sync_run_id: Optional[str],
    now_utc: str,
    changed: bool,
    text_hash: Optional[str] = None,
    normalizer_version: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Upsert the per-record state index (latest hash + last seen/changed)."""
    conn = _open(db_path)
    last_changed = now_utc if changed else None
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_live_record_state_index (
              record_key, project_key, endpoint_id, parent_procore_id, procore_record_id,
              current_canonical_hash, current_text_hash, first_seen_at_utc, last_seen_at_utc,
              last_changed_at_utc, last_snapshot_id, last_sync_run_id, normalizer_version,
              raw_body_persisted, redaction_applied
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
            ON CONFLICT(record_key) DO UPDATE SET
              last_seen_at_utc = excluded.last_seen_at_utc,
              current_canonical_hash = excluded.current_canonical_hash,
              current_text_hash = excluded.current_text_hash,
              last_snapshot_id = excluded.last_snapshot_id,
              last_sync_run_id = excluded.last_sync_run_id,
              normalizer_version = excluded.normalizer_version,
              last_changed_at_utc = COALESCE(
                excluded.last_changed_at_utc,
                procore_live_record_state_index.last_changed_at_utc
              )
            """,
            (
                record_key,
                project_key,
                endpoint_id,
                parent_procore_id or "",
                str(procore_record_id),
                canonical_hash,
                text_hash,
                now_utc,
                now_utc,
                last_changed,
                snapshot_id,
                sync_run_id,
                normalizer_version,
            ),
        )


def record_procore_history_for_record(
    *,
    project_key: str,
    endpoint_id: str,
    parent_procore_id: Optional[str],
    procore_record_id: str,
    normalized_fields: Mapping[str, Any],
    sync_run_id: Optional[str],
    now_utc: str,
    source_updated_at: Optional[str] = None,
    normalizer_version: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Sync-flow entry point run once per normalized record:

    current-state lookup -> hash compare -> snapshot if new/changed -> change
    events if changed -> timeline events if significant -> state-index upsert.
    """
    canonical_hash = compute_canonical_hash(normalized_fields)
    snap = record_procore_snapshot_if_changed(
        project_key=project_key,
        endpoint_id=endpoint_id,
        parent_procore_id=parent_procore_id,
        procore_record_id=procore_record_id,
        normalized_fields=normalized_fields,
        sync_run_id=sync_run_id,
        observed_at_utc=now_utc,
        source_updated_at=source_updated_at,
        normalizer_version=normalizer_version,
        canonical_hash=canonical_hash,
        db_path=db_path,
    )
    record_key = snap["record_key"]

    if not snap["changed"]:
        # Unchanged: bump last_seen only; no new snapshot / events.
        record_procore_current_state(
            record_key=record_key,
            project_key=project_key,
            endpoint_id=endpoint_id,
            parent_procore_id=parent_procore_id,
            procore_record_id=procore_record_id,
            canonical_hash=canonical_hash,
            snapshot_id=snap["snapshot_id"],
            sync_run_id=sync_run_id,
            now_utc=now_utc,
            changed=False,
            normalizer_version=normalizer_version,
            db_path=db_path,
        )
        return {"changed": False, "snapshot_id": snap["snapshot_id"], "change_events": 0, "timeline_events": 0}

    if snap["is_new"]:
        events = [
            ChangeEvent(
                field_path="*",
                change_type="added",
                change_category="record_created",
                old_value_redacted=None,
                new_value_redacted=None,
                old_value_hash=None,
                new_value_hash=canonical_hash[:16],
                importance="medium",
                review_required=False,
                significant=True,
            )
        ]
    else:
        events = diff_canonical_records(snap["previous_canonical"], dict(normalized_fields))

    change_count = record_procore_change_events(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        parent_procore_id=parent_procore_id,
        procore_record_id=procore_record_id,
        sync_run_id=sync_run_id,
        from_snapshot_id=snap["prev_snapshot_id"],
        to_snapshot_id=snap["snapshot_id"],
        detected_at_utc=now_utc,
        source_updated_at=source_updated_at,
        events=events,
        db_path=db_path,
    )
    timeline_count = record_procore_timeline_events(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        parent_procore_id=parent_procore_id,
        procore_record_id=procore_record_id,
        snapshot_id=snap["snapshot_id"],
        event_time_utc=source_updated_at or now_utc,
        events=events,
        db_path=db_path,
    )
    record_procore_current_state(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        parent_procore_id=parent_procore_id,
        procore_record_id=procore_record_id,
        canonical_hash=canonical_hash,
        snapshot_id=snap["snapshot_id"],
        sync_run_id=sync_run_id,
        now_utc=now_utc,
        changed=True,
        normalizer_version=normalizer_version,
        db_path=db_path,
    )
    return {
        "changed": True,
        "snapshot_id": snap["snapshot_id"],
        "is_new": snap["is_new"],
        "change_events": change_count,
        "timeline_events": timeline_count,
    }


# ---------------------------------------------------------------------------
# Read APIs
# ---------------------------------------------------------------------------


def get_procore_record_history(
    *, record_key: str, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Return all snapshots for a record, oldest first (full reconstruction)."""
    conn = _open(db_path)
    rows = conn.execute(
        """
        SELECT snapshot_id, record_key, observed_at_utc, source_updated_at_utc,
               canonical_hash, canonical_json_redacted, changed_from_previous,
               change_summary_json, normalizer_version
          FROM procore_live_record_snapshots
         WHERE record_key = ?
         ORDER BY observed_at_utc ASC, snapshot_id ASC
        """,
        (record_key,),
    ).fetchall()
    return [{k: row[k] for k in row.keys()} for row in rows]


def get_procore_changes(
    *,
    project_key: str,
    since_utc: Optional[str] = None,
    until_utc: Optional[str] = None,
    record_key: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return change events for a project (optionally a record / time window),
    newest first. Pass ``since_utc`` = now-48h to answer recent-change queries."""
    clauses = ["project_key = ?"]
    params: List[Any] = [project_key]
    if record_key is not None:
        clauses.append("record_key = ?")
        params.append(record_key)
    if since_utc is not None:
        clauses.append("detected_at_utc >= ?")
        params.append(since_utc)
    if until_utc is not None:
        clauses.append("detected_at_utc <= ?")
        params.append(until_utc)
    conn = _open(db_path)
    rows = conn.execute(
        f"""
        SELECT change_event_id, record_key, endpoint_id, procore_record_id, detected_at_utc,
               source_updated_at_utc, field_path, old_value_redacted, new_value_redacted,
               old_value_hash, new_value_hash, change_type, change_category, importance,
               review_required
          FROM procore_live_record_change_events
         WHERE {" AND ".join(clauses)}
         ORDER BY detected_at_utc DESC, change_event_id ASC
        """,
        params,
    ).fetchall()
    return [{k: row[k] for k in row.keys()} for row in rows]


def get_procore_timeline(
    *,
    project_key: str,
    since_utc: Optional[str] = None,
    until_utc: Optional[str] = None,
    endpoint_id: Optional[str] = None,
    record_key: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return assistant-ready timeline events for a project (optionally an
    endpoint / record / time window), newest first."""
    clauses = ["project_key = ?"]
    params: List[Any] = [project_key]
    if endpoint_id is not None:
        clauses.append("endpoint_id = ?")
        params.append(endpoint_id)
    if record_key is not None:
        clauses.append("record_key = ?")
        params.append(record_key)
    if since_utc is not None:
        clauses.append("event_time_utc >= ?")
        params.append(since_utc)
    if until_utc is not None:
        clauses.append("event_time_utc <= ?")
        params.append(until_utc)
    conn = _open(db_path)
    rows = conn.execute(
        f"""
        SELECT timeline_event_id, record_key, endpoint_id, procore_record_id, event_type,
               event_time_utc, summary_redacted, importance, actor_entity_key,
               target_entity_key, action_signal_id, source_change_event_id
          FROM procore_record_timeline_events
         WHERE {" AND ".join(clauses)}
         ORDER BY event_time_utc DESC, timeline_event_id ASC
        """,
        params,
    ).fetchall()
    return [{k: row[k] for k in row.keys()} for row in rows]


__all__ = [
    "ChangeEvent",
    "compute_canonical_hash",
    "diff_canonical_records",
    "get_procore_changes",
    "get_procore_record_history",
    "get_procore_timeline",
    "record_procore_change_events",
    "record_procore_current_state",
    "record_procore_history_for_record",
    "record_procore_snapshot_if_changed",
    "record_procore_timeline_events",
]
