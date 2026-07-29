"""Deterministic projection from email/calendar raw content rows into the V49 structured
parent + child tables.

Guarantees (mirroring the Procore projection engine discipline):

- **Registry-driven** — :mod:`projection_registry` decides every column, child table, and
  lossless sidecar; this module contains no per-field business logic beyond the registry.
- **Fail closed on unmapped fields** — if the completeness matrix reports any unmapped
  business field for a family, ``enforce`` mode raises ``UnknownProjectionPath`` and writes
  nothing for that family; ``live`` mode degrades the receipt (``ok=False``) without a
  partial projection (the raw rows remain the system of record).
- **Idempotent** — the parent upserts on ``projection_id``; child rows are deleted by parent
  and re-inserted, so replaying the same raw rows yields identical rows.
- **Source-quality precedence** — a lower-quality raw row never downgrades a higher-quality
  structured projection.
- **No raw value emission** — receipts carry counts and field *names* only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import get_connection, transaction

from . import projection_matrix as matrix
from . import projection_registry as reg
from .source_quality import classify_calendar, classify_email, rank

MODE_LIVE = "live"
MODE_ENFORCE = "enforce"


class UnknownProjectionPath(RuntimeError):
    def __init__(self, family: str, unknown: list[str]) -> None:
        self.family = family
        self.unknown = unknown
        super().__init__(f"{family}: {len(unknown)} unmapped business field path(s)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()


def _pid(prefix: str, raw_pk_value: str) -> str:
    return f"{prefix}-{_hash(raw_pk_value)[:32]}"


def _loads(value: Any, default: Any) -> Any:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return default
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
    return parsed


def _has_text(value: Any) -> bool:
    return bool(value is not None and str(value).strip() != "")


def _avail(value: Any) -> int:
    return 1 if _has_text(value) else 0


def _chars(value: Any) -> int:
    return len(str(value)) if _has_text(value) else 0


def _domain(address: Any) -> str | None:
    if not _has_text(address) or "@" not in str(address):
        return None
    return str(address).rsplit("@", 1)[-1].lower() or None


# --- generic write helpers --------------------------------------------------------


def _physical_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _upsert(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> None:
    cols = list(values.keys())
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(
        f"{c}=excluded.{c}" for c in cols if c not in {"projection_id", "created_utc"}
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(projection_id) DO UPDATE SET {assignments}"
    )
    conn.execute(sql, tuple(values[c] for c in cols))


def _existing_rank(conn: sqlite3.Connection, table: str, projection_id: str) -> int:
    try:
        row = conn.execute(
            f"SELECT source_quality FROM {table} WHERE projection_id = ?", (projection_id,)
        ).fetchone()
    except sqlite3.Error:
        return 0
    return rank(row[0]) if row else 0


def _delete_children(conn: sqlite3.Connection, table: str, parent_id: str) -> None:
    conn.execute(f"DELETE FROM {table} WHERE parent_projection_id = ?", (parent_id,))


# --- per-family value builders ----------------------------------------------------


def _email_message_values(
    row: dict[str, Any], now_utc: str
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    raw_id = row["raw_email_id"]
    pid = _pid("ecpm", raw_id)
    sq = row.get("source_quality") or classify_email(
        body_text=row.get("body_text"),
        body_html=row.get("body_html"),
        body_preview=row.get("body_preview"),
    )
    to = _loads(row.get("to_recipients_json"), [])
    cc = _loads(row.get("cc_recipients_json"), [])
    bcc = _loads(row.get("bcc_recipients_json"), [])
    att = _loads(row.get("attachment_metadata_json"), [])
    thread_ref = row.get("conversation_id_hash") or row.get("message_id_hash")
    recipient_count = (
        len(to) + len(cc) + len(bcc) + (1 if _has_text(row.get("from_address")) else 0)
    )
    values = {
        "projection_id": pid,
        "raw_row_id": raw_id,
        "raw_email_id": raw_id,
        "source_family": "email_message",
        "message_id_hash": row.get("message_id_hash"),
        "internet_message_id_hash": row.get("internet_message_id_hash"),
        "conversation_id_hash": row.get("conversation_id_hash"),
        "source_ref_hash": row.get("source_ref_hash"),
        "project_key": row.get("project_key"),
        "thread_ref": thread_ref,
        "subject": row.get("subject"),
        "from_name": row.get("from_name"),
        "from_address": row.get("from_address"),
        "sent_at_utc": row.get("sent_at_utc"),
        "received_at_utc": row.get("received_at_utc"),
        "has_attachments": int(row.get("has_attachments") or 0),
        "body_preview_available": _avail(row.get("body_preview")),
        "body_preview_chars": _chars(row.get("body_preview")),
        "body_text_available": _avail(row.get("body_text")),
        "body_text_chars": _chars(row.get("body_text")),
        "body_html_available": _avail(row.get("body_html")),
        "body_html_chars": _chars(row.get("body_html")),
        "recipient_count": recipient_count,
        "attachment_count": len(att) if isinstance(att, list) else 0,
        "source_quality": sq,
        "payload_hash": row.get("payload_hash"),
        "raw_capture_run_id": row.get("raw_capture_run_id"),
        "source_updated_at_utc": row.get("source_updated_at_utc"),
        "payload_sidecar_json": row.get("raw_sidecar_json"),
        "idempotency_key": row.get("payload_hash") or _hash(raw_id),
        "projection_schema_version": reg.PROJECTION_SCHEMA_VERSION,
        "security_scrub_status": "scrubbed",
        "is_current": 1,
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }
    recipients: list[dict[str, Any]] = []
    idx = 0
    if _has_text(row.get("from_address")) or _has_text(row.get("from_name")):
        recipients.append(
            _recipient_child(
                pid,
                raw_id,
                row.get("project_key"),
                sq,
                "from",
                row.get("from_name"),
                row.get("from_address"),
                "from",
                idx,
                now_utc,
            )
        )
        idx += 1
    for role, lst in (("to", to), ("cc", cc), ("bcc", bcc)):
        for rec in lst if isinstance(lst, list) else []:
            if not isinstance(rec, dict):
                continue
            recipients.append(
                _recipient_child(
                    pid,
                    raw_id,
                    row.get("project_key"),
                    sq,
                    role,
                    rec.get("name"),
                    rec.get("address"),
                    "%s_recipients_json[]" % role,
                    idx,
                    now_utc,
                )
            )
            idx += 1
    attachments: list[dict[str, Any]] = []
    for a_idx, a in enumerate(att if isinstance(att, list) else []):
        if not isinstance(a, dict):
            continue
        attachments.append(
            _base_child(
                pid,
                raw_id,
                row.get("project_key"),
                sq,
                "attachment_metadata_json[]",
                a_idx,
                now_utc,
                {
                    "name": a.get("name"),
                    "content_type": a.get("contentType") or a.get("content_type"),
                    "size_bytes": a.get("size"),
                    "is_inline": 1 if (a.get("isInline") or a.get("is_inline")) else 0,
                    "attachment_id": a.get("id") or a.get("attachment_id"),
                    "attachment_id_hash": a.get("attachment_id_hash"),
                },
            )
        )
    children = {
        "email_raw_message_recipients_structured": recipients,
        "email_raw_message_attachments_structured": attachments,
    }
    return values, children


def _recipient_child(
    parent_id, raw_id, project_key, sq, role, name, address, array_path, idx, now_utc
) -> dict[str, Any]:
    child = _base_child(
        parent_id,
        raw_id,
        project_key,
        sq,
        array_path,
        idx,
        now_utc,
        {"name": name, "address": address},
    )
    child["role"] = role
    child["domain"] = _domain(address)
    return child


def _base_child(
    parent_id, raw_id, project_key, sq, array_path, idx, now_utc, fields: dict[str, Any]
) -> dict[str, Any]:
    base = {
        "projection_id": _pid(
            "ecc",
            f"{parent_id}|{array_path}|{idx}|{fields.get('address') or fields.get('name') or fields.get('attachment_id') or idx}",
        ),
        "parent_projection_id": parent_id,
        "raw_row_id": raw_id,
        "source_family": None,
        "project_key": project_key,
        "child_index": idx,
        "array_path": array_path,
        "source_quality": sq,
        "is_current": 1,
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }
    base.update(fields)
    return base


def _email_thread_values(
    row: dict[str, Any], now_utc: str
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    raw_id = row["raw_thread_context_id"]
    pid = _pid("ecpt", raw_id)
    messages = _loads(row.get("messages_json"), [])
    any_body = any(
        isinstance(m, dict) and (_has_text(m.get("body_text")) or _has_text(m.get("body_html")))
        for m in (messages if isinstance(messages, list) else [])
    )
    sq = row.get("source_quality") or ("graph_full_body" if any_body else "metadata_only")
    values = {
        "projection_id": pid,
        "raw_row_id": raw_id,
        "raw_thread_context_id": raw_id,
        "source_family": "email_thread",
        "thread_ref": row.get("thread_ref"),
        "conversation_id_hash": row.get("conversation_id_hash"),
        "project_key": row.get("project_key"),
        "thread_subject": row.get("thread_subject"),
        "message_count": int(row.get("message_count") or 0),
        "participant_count": int(row.get("participant_count") or 0),
        "model_ready": int(row.get("model_ready") or 0),
        "has_full_body": 1 if any_body else 0,
        "source_quality": sq,
        "payload_hash": row.get("payload_hash"),
        "raw_capture_run_id": row.get("raw_capture_run_id"),
        "source_refs_sidecar_json": row.get("source_refs_json"),
        "idempotency_key": row.get("payload_hash") or _hash(raw_id),
        "projection_schema_version": reg.PROJECTION_SCHEMA_VERSION,
        "security_scrub_status": "scrubbed",
        "is_current": 1,
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }
    msg_rows: list[dict[str, Any]] = []
    for m_idx, m in enumerate(messages if isinstance(messages, list) else []):
        if not isinstance(m, dict):
            continue
        msg_rows.append(
            _base_child(
                pid,
                raw_id,
                row.get("project_key"),
                sq,
                "messages_json[]",
                m_idx,
                now_utc,
                {
                    "subject": m.get("subject"),
                    "from_name": m.get("from_name"),
                    "from_address": m.get("from_address"),
                    "message_received_at": m.get("received_at"),
                    "body_text_available": _avail(m.get("body_text")),
                    "body_text_chars": _chars(m.get("body_text")),
                    "body_html_available": _avail(m.get("body_html")),
                    "body_html_chars": _chars(m.get("body_html")),
                },
            )
        )
    return values, {"email_raw_thread_messages_structured": msg_rows}


def _calendar_event_values(
    row: dict[str, Any], now_utc: str
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    raw_id = row["raw_calendar_event_id"]
    pid = _pid("ecpc", raw_id)
    sq = row.get("source_quality") or classify_calendar(
        body_text=row.get("body_text"),
        body_html=row.get("body_html"),
        body_preview=row.get("body_preview"),
    )
    attendees = _loads(row.get("attendees_json"), [])
    recurrence = _loads(row.get("recurrence_json"), None)
    sidecar = _loads(row.get("raw_sidecar_json"), {})
    has_join = 1 if _has_text(row.get("join_url")) else 0
    values = {
        "projection_id": pid,
        "raw_row_id": raw_id,
        "raw_calendar_event_id": raw_id,
        "source_family": "calendar_event",
        "graph_event_id_hash": row.get("graph_event_id_hash"),
        "event_index_id": row.get("event_index_id"),
        "source_ref_hash": row.get("source_ref_hash"),
        "project_key": row.get("project_key"),
        "subject": row.get("subject"),
        "location_display": row.get("location_display"),
        "organizer_name": row.get("organizer_name"),
        "organizer_email": row.get("organizer_email"),
        "online_meeting_provider": row.get("online_meeting_provider"),
        "start_datetime_utc": row.get("start_datetime_utc"),
        "end_datetime_utc": row.get("end_datetime_utc"),
        "body_preview_available": _avail(row.get("body_preview")),
        "body_preview_chars": _chars(row.get("body_preview")),
        "body_text_available": _avail(row.get("body_text")),
        "body_text_chars": _chars(row.get("body_text")),
        "body_html_available": _avail(row.get("body_html")),
        "body_html_chars": _chars(row.get("body_html")),
        "has_join_url": has_join,
        "join_url_policy": row.get("join_url_policy") or "local_db_only",
        "attendee_count": len(attendees) if isinstance(attendees, list) else 0,
        "has_recurrence": 1 if recurrence else 0,
        "source_quality": sq,
        "payload_hash": row.get("payload_hash"),
        "raw_capture_run_id": row.get("raw_capture_run_id"),
        "source_updated_at_utc": row.get("source_updated_at_utc"),
        "payload_sidecar_json": row.get("raw_sidecar_json"),
        "recurrence_sidecar_json": row.get("recurrence_json") if recurrence else None,
        "idempotency_key": row.get("payload_hash") or _hash(raw_id),
        "projection_schema_version": reg.PROJECTION_SCHEMA_VERSION,
        "security_scrub_status": "scrubbed",
        "is_current": 1,
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }
    attendee_rows: list[dict[str, Any]] = []
    for a_idx, a in enumerate(attendees if isinstance(attendees, list) else []):
        if not isinstance(a, dict):
            continue
        child = _base_child(
            pid,
            raw_id,
            row.get("project_key"),
            sq,
            "attendees_json[]",
            a_idx,
            now_utc,
            {
                "attendee_type": a.get("type"),
                "response_status": a.get("status"),
                "name": a.get("name"),
                "address": a.get("address"),
            },
        )
        child["domain"] = _domain(a.get("address"))
        attendee_rows.append(child)

    recurrence_rows: list[dict[str, Any]] = []
    if isinstance(recurrence, dict) and recurrence:
        pattern = recurrence.get("pattern") or {}
        rng = recurrence.get("range") or {}
        rec_child = _base_child(
            pid,
            raw_id,
            row.get("project_key"),
            sq,
            "recurrence_json",
            0,
            now_utc,
            {
                "pattern_type": pattern.get("type"),
                "pattern_interval": pattern.get("interval"),
                "range_type": rng.get("type"),
                "range_start": rng.get("startDate"),
                "range_end": rng.get("endDate"),
                "number_of_occurrences": rng.get("numberOfOccurrences"),
                "recurrence_timezone": rng.get("recurrenceTimeZone"),
            },
        )
        rec_child["payload_sidecar_json"] = row.get("recurrence_json")
        recurrence_rows.append(rec_child)

    location_rows: list[dict[str, Any]] = []
    locs = sidecar.get("locations") if isinstance(sidecar, dict) else None
    for l_idx, loc in enumerate(locs if isinstance(locs, list) else []):
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address") or {}
        coord = loc.get("coordinates") or {}
        location_rows.append(
            _base_child(
                pid,
                raw_id,
                row.get("project_key"),
                sq,
                "raw_sidecar_json.locations[]",
                l_idx,
                now_utc,
                {
                    "display_name": loc.get("displayName"),
                    "location_type": loc.get("locationType"),
                    "location_uri": loc.get("locationUri"),
                    "address_street": addr.get("street"),
                    "address_city": addr.get("city"),
                    "address_state": addr.get("state"),
                    "address_country_or_region": addr.get("countryOrRegion"),
                    "address_postal_code": addr.get("postalCode"),
                    "coordinates_latitude": coord.get("latitude"),
                    "coordinates_longitude": coord.get("longitude"),
                },
            )
        )
    children = {
        "calendar_raw_event_attendees_structured": attendee_rows,
        "calendar_raw_event_recurrence_structured": recurrence_rows,
        "calendar_raw_event_locations_structured": location_rows,
    }
    return values, children


_FAMILY_BUILDERS = {
    "email_message": _email_message_values,
    "email_thread": _email_thread_values,
    "calendar_event": _calendar_event_values,
}


# --- family projection ------------------------------------------------------------


def _project_family(
    conn: sqlite3.Connection, plan: reg.SourceFamilyPlan, *, mode: str, now_utc: str
) -> dict[str, Any]:
    cov, _ = matrix.compute_family_coverage(conn, plan)
    unmapped = (
        cov.unmapped_primary_business_fields
        + cov.unmapped_nested_business_fields
        + cov.observed_nested_arrays_without_child_table_or_mapped_sidecar
    )
    receipt: dict[str, Any] = {
        "source_family": plan.family,
        "raw_parent_rows": cov.raw_parent_rows,
        "projected_parent_rows": 0,
        "child_rows_written": 0,
        "skipped_higher_quality": 0,
        "degraded_unmapped": 0,
        "source_quality_distribution": {},
        "status": "ok",
        "ok": True,
    }
    if cov.raw_parent_rows == 0:
        receipt["status"] = matrix.STATUS_NO_RAW_ROWS
        return receipt
    if unmapped > 0:
        samples = cov.unmapped_primary_samples + cov.unmapped_nested_samples
        if mode == MODE_ENFORCE:
            raise UnknownProjectionPath(plan.family, samples)
        receipt.update(
            {
                "status": matrix.STATUS_FAILED_UNMAPPED,
                "ok": False,
                "degraded_unmapped": unmapped,
                "unmapped_field_samples": samples[:20],
            }
        )
        return receipt

    builder = _FAMILY_BUILDERS[plan.family]
    raw_cols = [r[1] for r in conn.execute(f"PRAGMA table_info({plan.raw_table})")]
    structured_cols = _physical_columns(conn, plan.structured_table)
    child_cols = {t: _physical_columns(conn, t) for t in plan.required_child_columns()}

    dist: dict[str, int] = {}
    for db_row in conn.execute(f"SELECT {', '.join(raw_cols)} FROM {plan.raw_table}").fetchall():
        row = dict(zip(raw_cols, db_row, strict=True))
        parent_values, children = builder(row, now_utc)
        # physical-column parity guard (defensive; DDL is generated from the registry).
        missing = [k for k in parent_values if k not in structured_cols]
        if missing:
            if mode == MODE_ENFORCE:
                raise UnknownProjectionPath(
                    plan.family, [f"{plan.structured_table}.{m}" for m in missing]
                )
            receipt.update(
                {
                    "status": "schema_parity_broken",
                    "ok": False,
                    "missing_columns_sample": missing[:20],
                }
            )
            return receipt
        pid = parent_values["projection_id"]
        sq = parent_values["source_quality"]
        dist[sq] = dist.get(sq, 0) + 1
        if _existing_rank(conn, plan.structured_table, pid) > rank(sq):
            receipt["skipped_higher_quality"] += 1
            continue
        _upsert(conn, plan.structured_table, parent_values)
        receipt["projected_parent_rows"] += 1
        for table, rows in children.items():
            _delete_children(conn, table, pid)
            phys = child_cols.get(table) or _physical_columns(conn, table)
            for cvals in rows:
                cvals["source_family"] = plan.family
                cvals = {k: v for k, v in cvals.items() if k in phys}
                _upsert(conn, table, cvals)
                receipt["child_rows_written"] += 1
    receipt["source_quality_distribution"] = dist
    return receipt


# --- public API -------------------------------------------------------------------


def reprocess(
    *,
    db_path: str | Path | None = None,
    apply: bool = False,
    family: str | None = None,
    mode: str = MODE_ENFORCE,
    record_receipts: bool = True,
) -> dict[str, Any]:
    """Project raw email/calendar rows into the structured tables. ``apply=False`` is a
    dry run (no writes). Idempotent; honours source-quality precedence."""
    conn = get_connection(Path(db_path) if db_path is not None else None)
    plans = [p for p in reg.PLANS.values() if family in (None, p.family)]
    now_utc = _now()
    run_id = f"ecpr-{uuid.uuid4().hex[:24]}"
    families: list[dict[str, Any]] = []

    def _run(active: sqlite3.Connection) -> None:
        for plan in plans:
            families.append(_project_family(active, plan, mode=mode, now_utc=now_utc))

    if apply:
        with transaction(conn):
            _run(conn)
            if record_receipts:
                _record_receipts(conn, run_id, "apply", families, now_utc)
    else:
        # dry-run: compute coverage only, no writes.
        for plan in plans:
            cov, _ = matrix.compute_family_coverage(conn, plan)
            families.append(
                {
                    "source_family": plan.family,
                    "raw_parent_rows": cov.raw_parent_rows,
                    "projected_parent_rows_existing": cov.projected_parent_rows,
                    "would_project": cov.raw_parent_rows,
                    "status": cov.status,
                    "ok": cov.status
                    in (
                        matrix.STATUS_COMPLETE,
                        matrix.STATUS_COMPLETE_WITH_EXCLUSIONS,
                        matrix.STATUS_NO_RAW_ROWS,
                    ),
                }
            )

    ok = all(f.get("ok", True) for f in families)
    return {
        "command": "hb-assistant email-calendar raw projection-reprocess",
        "mode": "apply" if apply else "dry_run",
        "enforcement": mode,
        "run_id": run_id if apply else None,
        "ok": ok,
        "families": families,
        "live_graph_calls": 0,
        "external_writeback_performed": 0,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


def _record_receipts(
    conn: sqlite3.Connection, run_id: str, mode: str, families: list[dict[str, Any]], now_utc: str
) -> None:
    for fam in families:
        family = fam["source_family"]
        conn.execute(
            "INSERT OR REPLACE INTO email_calendar_projection_runs "
            "(run_id, source_family, mode, started_utc, completed_utc, raw_parent_rows, "
            " projected_parent_rows, child_rows_written, skipped_higher_quality, "
            " degraded_unmapped, source_quality_distribution_json, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"{run_id}-{family}",
                family,
                mode,
                now_utc,
                now_utc,
                fam.get("raw_parent_rows", 0),
                fam.get("projected_parent_rows", 0),
                fam.get("child_rows_written", 0),
                fam.get("skipped_higher_quality", 0),
                fam.get("degraded_unmapped", 0),
                json.dumps(fam.get("source_quality_distribution", {}), sort_keys=True),
                fam.get("status", "ok"),
            ),
        )
    for plan in reg.PLANS.values():
        cov, _ = matrix.compute_family_coverage(conn, plan)
        conn.execute(
            "INSERT OR REPLACE INTO email_calendar_projection_coverage "
            "(coverage_id, run_id, source_family, raw_table, structured_table, raw_parent_rows, "
            " projected_parent_rows, unmapped_primary_business_fields, "
            " unmapped_nested_business_fields, observed_nested_arrays_without_dest, status, computed_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"{run_id}-{plan.family}",
                run_id,
                plan.family,
                plan.raw_table,
                plan.structured_table,
                cov.raw_parent_rows,
                cov.projected_parent_rows,
                cov.unmapped_primary_business_fields,
                cov.unmapped_nested_business_fields,
                cov.observed_nested_arrays_without_child_table_or_mapped_sidecar,
                cov.status,
                now_utc,
            ),
        )


def coverage(*, db_path: str | Path | None = None) -> dict[str, Any]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    return matrix.compute_coverage(conn)


def status(*, db_path: str | Path | None = None) -> dict[str, Any]:
    """Raw + structured row counts and source-quality distribution (counts only)."""
    conn = get_connection(Path(db_path) if db_path is not None else None)

    def _count(table: str) -> int:
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.Error:
            return 0

    def _sq(table: str) -> dict[str, int]:
        try:
            return {
                r[0]: r[1]
                for r in conn.execute(
                    f"SELECT source_quality, COUNT(*) FROM {table} GROUP BY source_quality"
                )
            }
        except sqlite3.Error:
            return {}

    families = []
    for plan in reg.PLANS.values():
        families.append(
            {
                "source_family": plan.family,
                "raw_table": plan.raw_table,
                "raw_rows": _count(plan.raw_table),
                "raw_source_quality": _sq(plan.raw_table),
                "structured_table": plan.structured_table,
                "structured_rows": _count(plan.structured_table),
                "structured_source_quality": _sq(plan.structured_table),
            }
        )
    return {
        "command": "hb-assistant email-calendar raw status",
        "ok": True,
        "families": families,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


def inventory(*, db_path: str | Path | None = None) -> dict[str, Any]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    rows = matrix.matrix_rows_for_db(conn)
    return {
        "command": "hb-assistant email-calendar raw projection-inventory",
        "ok": True,
        "row_count": len(rows),
        "rows": [matrix.matrix_row_as_csv(r) for r in rows],
        "header": matrix.MATRIX_CSV_HEADER,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


__all__ = [
    "MODE_ENFORCE",
    "MODE_LIVE",
    "UnknownProjectionPath",
    "coverage",
    "inventory",
    "reprocess",
    "status",
]

# Apple MCC contacts projections use apple_mcc.contacts.projection_registry.
