"""Contact email/phone hash index writers."""

from __future__ import annotations

import hashlib
import sqlite3

from hb_assistant.apple_mcc.identity.contact_revision import (
    contact_email_hash_row_id,
    contact_phone_hash_row_id,
    normalize_email_for_hash,
    normalize_phone_for_hash,
)

NORM_VERSION = "norm_v1"


def email_value_hash(email: str) -> str:
    return hashlib.sha256(normalize_email_for_hash(email).encode("utf-8")).hexdigest()


def phone_value_hash(phone: str) -> str:
    return hashlib.sha256(normalize_phone_for_hash(phone).encode("utf-8")).hexdigest()


def upsert_email_hash(
    conn: sqlite3.Connection,
    *,
    entity_id: str,
    email: str,
    label: str = "",
    is_primary: int = 0,
) -> str:
    h = email_value_hash(email)
    row_id = contact_email_hash_row_id(entity_id, h, label, NORM_VERSION)
    conn.execute(
        """
        INSERT OR IGNORE INTO contact_email_hashes (
          hash_row_id, hash, contact_entity_id, label, norm_version, is_primary
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row_id, h, entity_id, label, NORM_VERSION, is_primary),
    )
    return row_id


def upsert_phone_hash(
    conn: sqlite3.Connection,
    *,
    entity_id: str,
    phone: str,
    label: str = "",
    is_primary: int = 0,
) -> str:
    h = phone_value_hash(phone)
    row_id = contact_phone_hash_row_id(entity_id, h, label, NORM_VERSION)
    conn.execute(
        """
        INSERT OR IGNORE INTO contact_phone_hashes (
          hash_row_id, hash, contact_entity_id, label, norm_version, is_primary
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row_id, h, entity_id, label, NORM_VERSION, is_primary),
    )
    return row_id
