"""V49 schema + email/calendar raw ingestion hardening (Pass 1).

Fixture-only; synthetic body/agenda sentinels never appear in any committed snapshot.
Proves: additive V49 migration applies + is idempotent, the source-quality/provenance
columns and structured/receipt tables exist, full bodies persist locally, source-quality is
classified, a lower-quality re-capture cannot downgrade local-private body content at the
store layer, attachment metadata persists (content does not), raw access events are recorded,
and no serialized outbound surface emits a raw body/agenda/join-URL sentinel.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.email_calendar import projection_engine as eng
from hb_assistant.construction.email_calendar import projection_registry as reg
from hb_assistant.construction.email_calendar import schema
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

BODY_SENTINEL = "BODY_SENTINEL_zqx"
AGENDA_SENTINEL = "AGENDA_SENTINEL_zqx"
JOIN_SENTINEL = "https://teams.microsoft.com/l/JOIN_SENTINEL_zqx"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "ec.sqlite"))


def _conn(store: ConstructionStore) -> sqlite3.Connection:
    conn = sqlite3.connect(store._db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --- schema -----------------------------------------------------------------------


def test_v49_applies_and_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION == 49
    assert SQLiteMigrator(db_path=str(db)).apply() == 49
    conn = sqlite3.connect(str(db))
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 49").fetchone()[0]
    assert count == 1


def test_v49_adds_source_quality_and_provenance_columns(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    email = {r[1] for r in conn.execute("PRAGMA table_info(email_message_raw_content)")}
    assert {
        "source_quality",
        "payload_hash",
        "raw_capture_run_id",
        "source_updated_at_utc",
        "raw_content_schema_version",
        "raw_sidecar_json",
    } <= email
    cal = {r[1] for r in conn.execute("PRAGMA table_info(calendar_event_raw_content)")}
    assert {"source_quality", "join_url_policy", "raw_sidecar_json", "payload_hash"} <= cal
    thread = {r[1] for r in conn.execute("PRAGMA table_info(email_thread_raw_context)")}
    assert {"source_quality", "payload_hash"} <= thread


def test_v49_creates_structured_and_receipt_tables(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(reg.all_structured_tables()) <= tables
    for receipt in (
        "email_calendar_raw_ingestion_runs",
        "raw_content_source_quality_snapshots",
        "email_calendar_projection_runs",
        "email_calendar_projection_coverage",
    ):
        assert receipt in tables


def test_v49_preserves_legacy_and_v48_tables(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # legacy redacted tables + V42 raw tables + a V46/47 Procore table all intact
    assert {"email_messages", "calendar_event_index", "email_message_raw_content"} <= tables
    assert any(t.startswith("procore_") for t in tables)


def test_structured_ddl_parity_with_registry(tmp_path: Path) -> None:
    """Every registry-required curated column physically exists (no engine write can drift)."""
    db = tmp_path / "m.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    required = schema.required_columns_by_table()
    for table, cols in required.items():
        physical = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        missing = [c for c in cols if c not in physical]
        assert not missing, f"{table} missing registry columns: {missing}"


# --- ingestion --------------------------------------------------------------------


def test_full_text_body_persists_and_is_classified(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1",
        message_id_hash="h1",
        subject="s",
        body_text=BODY_SENTINEL,
        from_address="a@hb.com",
    )
    row = (
        _conn(store)
        .execute("SELECT body_text, source_quality FROM email_message_raw_content")
        .fetchone()
    )
    assert row["body_text"] == BODY_SENTINEL
    assert row["source_quality"] == "graph_full_body"


def test_full_html_body_persists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1", message_id_hash="h1", body_html=f"<p>{BODY_SENTINEL}</p>"
    )
    row = (
        _conn(store)
        .execute("SELECT body_html, source_quality FROM email_message_raw_content")
        .fetchone()
    )
    assert BODY_SENTINEL in row["body_html"]
    assert row["source_quality"] == "graph_full_body"


def test_preview_only_classified(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1", message_id_hash="h1", body_preview="just a preview"
    )
    row = _conn(store).execute("SELECT source_quality FROM email_message_raw_content").fetchone()
    assert row["source_quality"] == "graph_body_preview_only"


def test_lower_quality_cannot_overwrite_full_body(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1",
        message_id_hash="h1",
        body_text=BODY_SENTINEL,
        source_quality="graph_full_body",
    )
    # a later metadata-only re-capture must NOT erase the full body
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1",
        message_id_hash="h1",
        body_text=None,
        project_key="p2",
        source_quality="metadata_only",
    )
    row = (
        _conn(store)
        .execute("SELECT body_text, source_quality, project_key FROM email_message_raw_content")
        .fetchone()
    )
    assert row["body_text"] == BODY_SENTINEL
    assert row["source_quality"] == "graph_full_body"
    assert row["project_key"] == "p2"  # provenance/metadata still updates


def test_attachment_metadata_persists_without_content(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1",
        message_id_hash="h1",
        has_attachments=1,
        attachment_metadata_json=json.dumps(
            [{"name": "plan.pdf", "contentType": "application/pdf", "size": 10, "id": "a1"}]
        ),
    )
    cols = {r[1] for r in _conn(store).execute("PRAGMA table_info(email_message_raw_content)")}
    # the raw table has no attachment-content column anywhere
    assert not any("content_bytes" in c or c == "contentBytes" for c in cols)
    row = (
        _conn(store)
        .execute("SELECT attachment_metadata_json FROM email_message_raw_content")
        .fetchone()
    )
    assert "plan.pdf" in row["attachment_metadata_json"]


def test_calendar_full_event_persists_with_join_url_policy(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        subject="standup",
        body_text=AGENDA_SENTINEL,
        join_url=JOIN_SENTINEL,
        attendees_json=json.dumps(
            [{"type": "required", "status": "none", "name": "B", "address": "b@x.com"}]
        ),
    )
    row = (
        _conn(store)
        .execute(
            "SELECT body_text, source_quality, join_url, join_url_policy "
            "FROM calendar_event_raw_content"
        )
        .fetchone()
    )
    assert row["body_text"] == AGENDA_SENTINEL
    assert row["source_quality"] == "graph_full_event_body"
    assert row["join_url"] == JOIN_SENTINEL  # retained locally
    assert row["join_url_policy"] == "local_db_only"


def test_calendar_lower_quality_cannot_downgrade(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        body_text=AGENDA_SENTINEL,
        source_quality="graph_full_event_body",
    )
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        body_text=None,
        source_quality="metadata_only",
    )
    row = (
        _conn(store)
        .execute("SELECT body_text, source_quality FROM calendar_event_raw_content")
        .fetchone()
    )
    assert row["body_text"] == AGENDA_SENTINEL
    assert row["source_quality"] == "graph_full_event_body"


def test_raw_access_event_recorded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    eid = store.record_raw_content_access_event(
        source_family="email",
        endpoint_or_command="email.index.include_raw_content",
        source_ref_hash="h1",
        purpose="raw_email_ingestion",
    )
    assert eid
    row = (
        _conn(store)
        .execute(
            "SELECT source_family, raw_content_included, purpose FROM raw_content_access_events"
        )
        .fetchone()
    )
    assert row["source_family"] == "email"
    assert row["raw_content_included"] == 1
    assert row["purpose"] == "raw_email_ingestion"


def test_ingestion_run_receipt_has_no_body(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_email_calendar_raw_ingestion_run(
        run_id="r1",
        source_family="email",
        mode="apply",
        items_seen=2,
        items_raw_persisted=2,
        source_quality_distribution_json=json.dumps({"graph_full_body": 2}),
    )
    row = (
        _conn(store)
        .execute(
            "SELECT items_raw_persisted, raw_body_emitted, external_writeback_performed "
            "FROM email_calendar_raw_ingestion_runs"
        )
        .fetchone()
    )
    assert row["items_raw_persisted"] == 2
    assert row["raw_body_emitted"] == 0
    assert row["external_writeback_performed"] == 0


def test_run_receipt_guard_rejects_raw_body_emitted(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO email_calendar_raw_ingestion_runs "
            "(run_id, source_family, mode, raw_body_emitted) VALUES ('x','email','apply',1)"
        )


def test_outbound_serializers_do_not_emit_raw_body(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:1", message_id_hash="h1", subject="s", body_text=BODY_SENTINEL
    )
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        body_text=AGENDA_SENTINEL,
        join_url=JOIN_SENTINEL,
    )
    cov = eng.coverage(db_path=store._db_path)
    rep = eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    inv = eng.inventory(db_path=store._db_path)
    blob = json.dumps([cov, rep, inv])
    for sentinel in (BODY_SENTINEL, AGENDA_SENTINEL, "JOIN_SENTINEL"):
        assert sentinel not in blob
