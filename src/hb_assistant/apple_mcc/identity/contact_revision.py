"""Contact entity and revision identity formulas."""

from __future__ import annotations

import hashlib
import unicodedata


def _h(prefix: bytes, *parts: bytes) -> str:
    b = prefix
    for p in parts:
        b += p
    return hashlib.sha256(b).hexdigest()


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def container_locator_hash(container_name: str) -> str:
    return _h(b"cn_container_v1", nfc(container_name).encode("utf-8"))


def contact_id_hash(container_hex: str, cn_contact_id: str) -> str:
    return _h(b"cn_id_v1", bytes.fromhex(container_hex), b"\0", cn_contact_id.encode("utf-8"))


def contact_entity_id(container_hex: str, contact_id_hex: str) -> str:
    return _h(b"contact_entity_v1", bytes.fromhex(container_hex), b"\0", bytes.fromhex(contact_id_hex))


def contact_revision_key(entity_hex: str, payload_hash_hex: str) -> str:
    return _h(b"rev_contact_v1", bytes.fromhex(entity_hex), b"\0", bytes.fromhex(payload_hash_hex))


def contact_raw_snapshot_id(revision_key_hex: str) -> str:
    return _h(b"raw_contact_payload_v1", revision_key_hex.encode("utf-8"))


def contact_email_hash_row_id(entity_hex: str, email_hash: str, label: str, norm_version: str) -> str:
    return _h(
        b"ceh_v1",
        bytes.fromhex(entity_hex),
        b"\0",
        bytes.fromhex(email_hash) if len(email_hash) == 64 else email_hash.encode("utf-8"),
        b"\0",
        label.encode("utf-8"),
        b"\0",
        norm_version.encode("utf-8"),
    )


def contact_phone_hash_row_id(entity_hex: str, phone_hash: str, label: str, norm_version: str) -> str:
    # Plan: cph = sha256(b"cph_v1"+entity_hex.encode()+b"\0"+hash_hex.encode()+b"\0"+label+b"\0"+norm)
    return hashlib.sha256(
        b"cph_v1"
        + entity_hex.encode("utf-8")
        + b"\0"
        + phone_hash.encode("utf-8")
        + b"\0"
        + label.encode("utf-8")
        + b"\0"
        + norm_version.encode("utf-8")
    ).hexdigest()


def contact_linkage_id(left: str, right: str | None, kind: str) -> str:
    if kind == "unmatched" or right is None:
        return _h(b"link_v1", bytes.fromhex(left), b"\0unmatched")
    a, b = sorted([left, right])
    return _h(b"link_v1", bytes.fromhex(a), b"\0", bytes.fromhex(b), b"\0", kind.encode("utf-8"))


def contact_projection_id(raw_id: str, schema_ver: str) -> str:
    return _h(b"proj_contact_v1", raw_id.encode("utf-8"), b"\0", schema_ver.encode("utf-8"))


def contact_payload_hash(structured_payload_json: str) -> str:
    return hashlib.sha256(structured_payload_json.encode("utf-8")).hexdigest()


def normalize_email_for_hash(email: str) -> str:
    return email.strip().lower()


def normalize_phone_for_hash(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit() or ch == "+")
