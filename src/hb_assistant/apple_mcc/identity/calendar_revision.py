"""Calendar occurrence and revision identity formulas."""

from __future__ import annotations

import hashlib


def _h(prefix: bytes, *parts: bytes) -> str:
    b = prefix
    for p in parts:
        b += p
    return hashlib.sha256(b).hexdigest()


def source_locator_hash(source_title: str) -> str:
    return _h(b"ek_src_v1", source_title.encode("utf-8"))


def calendar_locator_hash(source_hex: str, calendar_id: str) -> str:
    return _h(b"ek_cal_v1", bytes.fromhex(source_hex), b"\0", calendar_id.encode("utf-8"))


def event_local_id_hash(calendar_hex: str, ek_event_id: str) -> str:
    return _h(b"ek_evt_v1", bytes.fromhex(calendar_hex), b"\0", ek_event_id.encode("utf-8"))


def occurrence_key(
    calendar_hex: str,
    *,
    ical_uid: str | None,
    ek_event_id: str,
    start_utc: str | None,
    recurrence_exception_id: str | None = None,
) -> str:
    uid = ical_uid or ek_event_id
    return _h(
        b"occ_v1",
        bytes.fromhex(calendar_hex),
        b"\0",
        uid.encode("utf-8"),
        b"\0",
        (start_utc or "").encode("utf-8"),
        b"\0",
        (recurrence_exception_id or "").encode("utf-8"),
    )


def calendar_revision_key(occurrence_key_hex: str, payload_hash_hex: str) -> str:
    return _h(b"rev_cal_v1", bytes.fromhex(occurrence_key_hex), b"\0", bytes.fromhex(payload_hash_hex))


def calendar_raw_snapshot_id(revision_key_hex: str) -> str:
    return _h(b"raw_cal_snap_v1", revision_key_hex.encode("utf-8"))


def apple_absent_graph_event_id_hash(source_local_id_hash_hex: str) -> str:
    return _h(b"apple_ek_absent_v1", source_local_id_hash_hex.encode("utf-8"))


def calendar_payload_hash(
    *,
    subject: str | None,
    body_text: str | None,
    body_html: str | None,
    body_preview: str | None,
    start_datetime_utc: str | None,
    end_datetime_utc: str | None,
    location_display: str | None,
) -> str:
    parts = [
        subject or "",
        body_text or "",
        body_html or "",
        body_preview or "",
        start_datetime_utc or "",
        end_datetime_utc or "",
        location_display or "",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
