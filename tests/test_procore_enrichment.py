"""Phase 04B cross-endpoint enrichment extractors — unit tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import (
    emit_action_signal,
    emit_record_edge,
    emit_text_intelligence,
    extract_attachment_refs,
    extract_company_refs,
    extract_custom_field_values,
    extract_location_refs,
    extract_people_refs,
)

_NOW = "2026-05-29T00:00:00Z"
_PERSON = {"id": 160586, "login": "synthetic-carl@example.test", "name": "Synthetic Carl"}


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _rows(db: Path, table: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# people
# --------------------------------------------------------------------------- #


def test_people_extraction_hashes_pii_and_dedups() -> None:
    db = _db()
    k1 = extract_people_refs(_PERSON, now_utc=_NOW, db_path=db)
    k2 = extract_people_refs(
        _PERSON, now_utc="2026-05-30T00:00:00Z", db_path=db
    )  # same person, later
    assert k1 == k2
    rows = _rows(db, "procore_people_entities")
    assert len(rows) == 1
    row = rows[0]
    assert row["procore_user_id"] == "160586"
    assert row["login_hash"] and row["login_hash"] != _PERSON["login"]
    assert row["display_name_redacted"] is None  # name never stored
    assert row["source_count"] == 2
    # no raw PII anywhere in the row
    blob = "|".join("" if v is None else str(v) for v in row)
    assert "synthetic-carl@example.test" not in blob and "Synthetic Carl" not in blob


# --------------------------------------------------------------------------- #
# company (vendor / responsible_contractor / company)
# --------------------------------------------------------------------------- #


def test_company_extraction_keeps_org_name_and_dedups() -> None:
    db = _db()
    extract_company_refs(
        {"id": 161072, "name": "Synthetic Architecture"}, now_utc=_NOW, db_path=db
    )  # vendor
    extract_company_refs(
        {
            "name": "Synthetic Architecture",
            "company": {"id": 161072, "name": "Synthetic Architecture"},
        },
        now_utc=_NOW,
        db_path=db,
    )  # responsible_contractor wrapping the same company (no top-level id) -> same key
    rows = _rows(db, "procore_company_entities")
    assert len(rows) == 1
    assert rows[0]["name_redacted"] == "Synthetic Architecture"
    assert rows[0]["source_count"] == 2


# --------------------------------------------------------------------------- #
# location
# --------------------------------------------------------------------------- #


def test_location_extraction_from_nested_payload() -> None:
    db = _db()
    loc = {
        "id": 15504,
        "name": "North Building>First Floor",
        "node_name": "Closet",
        "parent_id": 788866,
    }
    extract_location_refs(loc, project_key="tropical", now_utc=_NOW, db_path=db)
    rows = _rows(db, "procore_location_entities")
    assert len(rows) == 1
    assert rows[0]["procore_location_id"] == "15504"
    assert rows[0]["node_name_redacted"] == "Closet"
    assert rows[0]["parent_location_id"] == "788866"


# --------------------------------------------------------------------------- #
# attachments — no signed query strings persisted
# --------------------------------------------------------------------------- #


def test_attachment_extraction_strips_query_strings() -> None:
    db = _db()
    atts = [
        {
            "id": 42,
            "filename": "synthetic-photo.jpg",
            "content_type": "image/jpeg",
            "size": 1234,
            "url": "https://example.test/rest/v1.0/local_files/abc?company_id=15&prostore_file_id=76094",
            "share_url": "https://example.test/share/abc?token=secret",
            "viewable_url": "https://example.test/15/project/show?prostore_file_id=76094",
        }
    ]
    extract_attachment_refs(
        atts,
        project_key="tropical",
        source_record_key="tropical|meetings||1",
        source_endpoint_id="meetings",
        now_utc=_NOW,
        db_path=db,
    )
    rows = _rows(db, "procore_attachment_refs")
    assert len(rows) == 1
    row = rows[0]
    assert row["procore_attachment_id"] == "42"
    assert row["filename_redacted"] is None and row["filename_hash"]
    assert row["url_hash"] and row["url_path_redacted"] == "/rest/v1.0/local_files/abc"
    assert row["content_type"] == "image/jpeg" and row["size_bytes"] == 1234
    assert row["download_eligibility"] == "metadata_only"
    blob = "|".join("" if v is None else str(v) for v in row)
    assert (
        "?" not in blob
        and "company_id" not in blob
        and "prostore_file_id" not in blob
        and "token=" not in blob
    )


# --------------------------------------------------------------------------- #
# custom fields by data type
# --------------------------------------------------------------------------- #


def test_custom_fields_by_data_type_policy() -> None:
    db = _db()
    cfs = {
        "custom_field_bool": {"data_type": "boolean", "value": True},
        "custom_field_int": {"data_type": "integer", "value": 7},
        "custom_field_dec": {"data_type": "decimal", "value": 2.2},
        "custom_field_dt": {"data_type": "datetime", "value": "2026-05-19T12:00:00Z"},
        "custom_field_lov1": {"data_type": "lov_entry", "value": {"id": 1, "label": "Open"}},
        "custom_field_lovn": {
            "data_type": "lov_entries",
            "value": [{"id": 2, "label": "Open"}, {"id": 3, "label": "Late"}],
        },
        "custom_field_str": {"data_type": "string", "value": "secret free text value"},
        "custom_field_rich": {"data_type": "rich_text", "value": "<b>secret</b>"},
        "custom_field_login": {
            "data_type": "login_information",
            "value": {"login": "synthetic@example.test"},
        },
        "custom_field_files": {
            "data_type": "prostore_files",
            "value": [{"url": "https://example.test/f?token=x"}],
        },
        "custom_field_unk": {"data_type": "mystery", "value": "whatever"},
    }
    extract_custom_field_values(
        cfs,
        project_key="tropical",
        record_key="tropical|manpower||1",
        endpoint_id="daily-log-manpower",
        procore_record_id="1",
        now_utc=_NOW,
        db_path=db,
    )
    by_key = {r["custom_field_key"]: r for r in _rows(db, "procore_custom_field_values")}
    assert len(by_key) == 11
    # preserved types carry value_json_redacted, no hash
    assert json.loads(by_key["custom_field_bool"]["value_json_redacted"]) is True
    assert by_key["custom_field_bool"]["value_hash"] is None
    assert by_key["custom_field_lov1"]["value_label_redacted"] == "Open"
    assert by_key["custom_field_lovn"]["value_label_redacted"] == "Open, Late"
    # hashed types carry value_hash, no raw value
    for k in (
        "custom_field_str",
        "custom_field_rich",
        "custom_field_login",
        "custom_field_files",
        "custom_field_unk",
    ):
        assert by_key[k]["value_hash"] is not None
        assert by_key[k]["value_json_redacted"] is None
    # no raw secret / signed url anywhere
    blob = json.dumps([dict(r) for r in by_key.values()])
    assert "secret free text value" not in blob and "synthetic@example.test" not in blob
    assert "token=" not in blob and "?" not in blob


# --------------------------------------------------------------------------- #
# edges / signals / text intelligence
# --------------------------------------------------------------------------- #


def test_record_edge_idempotent() -> None:
    db = _db()
    e1 = emit_record_edge(
        project_key="tropical",
        from_record_key="tropical|rfis||1",
        edge_type="assignee",
        source_endpoint_id="rfis",
        to_entity_key="person:abc",
        now_utc=_NOW,
        db_path=db,
    )
    e2 = emit_record_edge(
        project_key="tropical",
        from_record_key="tropical|rfis||1",
        edge_type="assignee",
        source_endpoint_id="rfis",
        to_entity_key="person:abc",
        now_utc="2026-05-30T00:00:00Z",
        db_path=db,
    )
    assert e1 == e2
    assert len(_rows(db, "procore_record_edges")) == 1


def test_action_signal_written_and_idempotent() -> None:
    db = _db()
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|observations||9",
        endpoint_id="observations",
        signal_type="safety_open",
        importance="high",
        now_utc=_NOW,
        db_path=db,
    )
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|observations||9",
        endpoint_id="observations",
        signal_type="safety_open",
        importance="high",
        signal_status="resolved",
        now_utc=_NOW,
        db_path=db,
    )
    rows = _rows(db, "procore_action_signals")
    assert len(rows) == 1
    assert rows[0]["title_redacted"] == "safety_open"  # defaulted from signal_type
    assert rows[0]["signal_status"] == "resolved"  # updated on conflict


def test_text_intelligence_hash_only_and_idempotent() -> None:
    db = _db()
    secret = "the owner threatened a delay claim over the partition scope"
    emit_text_intelligence(
        project_key="tropical",
        record_key="tropical|rfis||1",
        endpoint_id="rfis",
        source_field_path="comment",
        text=secret,
        topics=["claim", "delay"],
        now_utc=_NOW,
        db_path=db,
    )
    emit_text_intelligence(
        project_key="tropical",
        record_key="tropical|rfis||1",
        endpoint_id="rfis",
        source_field_path="comment",
        text=secret,
        topics=["claim", "delay"],
        now_utc=_NOW,
        db_path=db,
    )
    rows = _rows(db, "procore_text_intelligence")
    assert len(rows) == 1
    row = rows[0]
    assert row["text_hash"] and row["text_length"] == len(secret)
    assert row["excerpt_redacted"] is None
    blob = "|".join("" if v is None else str(v) for v in row)
    assert secret not in blob  # raw text never stored
    assert json.loads(row["topics_json"]) == ["claim", "delay"]


def test_empty_text_returns_none() -> None:
    db = _db()
    assert (
        emit_text_intelligence(
            project_key="tropical",
            record_key="r",
            endpoint_id="rfis",
            source_field_path="comment",
            text="   ",
            now_utc=_NOW,
            db_path=db,
        )
        is None
    )
    assert _rows(db, "procore_text_intelligence") == []
