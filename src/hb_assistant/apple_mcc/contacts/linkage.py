"""Contact linkage outcomes."""

from __future__ import annotations

import sqlite3

from hb_assistant.apple_mcc.identity.contact_revision import contact_linkage_id
from hb_assistant.construction.store.repositories import rewrite_unmatched_linkage


def mark_unmatched(conn: sqlite3.Connection, *, entity_id: str, created_utc: str) -> str:
    lid = contact_linkage_id(entity_id, None, "unmatched")
    rewrite_unmatched_linkage(
        conn,
        left_contact_entity_id=entity_id,
        evidence_json="{}",
        created_utc=created_utc,
        linkage_id=lid,
    )
    return lid
