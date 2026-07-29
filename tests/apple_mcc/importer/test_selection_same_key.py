"""Same-key selection asserts for all families."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.apple_mcc.contracts.raw_fields import (
    CalendarObservationFields,
    CalendarRawFields,
    ContactObservationFields,
    ContactRawFields,
    EmailObservationFields,
    EmailRawFields,
)
from hb_assistant.apple_mcc.identity.calendar_revision import (
    apple_absent_graph_event_id_hash,
    calendar_payload_hash,
    calendar_raw_snapshot_id,
    calendar_revision_key,
    occurrence_key,
    source_locator_hash,
    calendar_locator_hash,
    event_local_id_hash,
)
from hb_assistant.apple_mcc.identity.contact_revision import (
    contact_entity_id,
    contact_id_hash,
    contact_payload_hash,
    contact_raw_snapshot_id,
    contact_revision_key,
    container_locator_hash,
)
from hb_assistant.apple_mcc.identity.email_revision import (
    account_locator_hash,
    canonical_message_key,
    email_payload_hash,
    email_raw_snapshot_id,
    email_revision_key,
    mailbox_locator_hash,
    mail_local_id_hash,
)
from hb_assistant.construction.store.repositories import (
    import_calendar_observation_and_revision,
    import_contact_observation_and_revision,
    import_email_observation_and_revision,
)


def test_email_same_key_and_no_downgrade(disposable_db: Path) -> None:
    conn = sqlite3.connect(str(disposable_db))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        acct = account_locator_hash("BF-Personal")
        mbx = mailbox_locator_hash(acct, "INBOX")
        local = mail_local_id_hash(acct, mbx, "msg-1")
        csk = canonical_message_key(internet_message_id="<a@b.com>", account_hex=acct, local_id_hex=local)
        ph = email_payload_hash(subject="S", body_text="body", body_html=None, body_preview=None, to_recipients_json="[]")
        rev = email_revision_key(csk, ph)
        snap = email_raw_snapshot_id(rev)
        raw = EmailRawFields(
            raw_email_id=snap,
            message_id_hash=local,
            internet_message_id_hash=csk,
            subject="S",
            body_text="body",
            source_quality="apple_mail_full_mime",
            payload_hash=ph,
        )
        obs = EmailObservationFields(
            observation_id="obs1",
            account_locator_hash=acct,
            source_local_id_hash=local,
            mailbox_locator_hash=mbx,
        )
        import_email_observation_and_revision(
            conn,
            observation_fields=obs,
            revision_key=rev,
            canonical_message_key=csk,
            payload_hash=ph,
            raw_email=raw,
            source_quality="apple_mail_full_mime",
            fidelity_class="full_mime",
            provider="apple_mail",
            observed_at_utc="2026-07-29T12:00:00Z",
        )
        # lower rank should not win selection
        ph2 = email_payload_hash(subject="S", body_text="body2", body_html=None, body_preview=None, to_recipients_json="[]")
        rev2 = email_revision_key(csk, ph2)
        snap2 = email_raw_snapshot_id(rev2)
        raw2 = EmailRawFields(
            raw_email_id=snap2,
            message_id_hash=local,
            subject="S",
            body_text="body2",
            source_quality="metadata_only",
            payload_hash=ph2,
        )
        obs2 = EmailObservationFields(
            observation_id="obs2",
            account_locator_hash=acct,
            source_local_id_hash=local + "x" if False else ("22" * 32),
            mailbox_locator_hash=mbx,
        )
        # use different local id hash for unique observation key
        obs2 = EmailObservationFields(
            observation_id="obs2",
            account_locator_hash=acct,
            source_local_id_hash="22" * 32,
            mailbox_locator_hash=mbx,
        )
        import_email_observation_and_revision(
            conn,
            observation_fields=obs2,
            revision_key=rev2,
            canonical_message_key=csk,
            payload_hash=ph2,
            raw_email=raw2,
            source_quality="metadata_only",
            fidelity_class="metadata",
            provider="apple_mail",
            observed_at_utc="2026-07-29T12:01:00Z",
        )
        sel = conn.execute(
            "SELECT selected_revision_key FROM email_message_current_selection WHERE canonical_message_key=?",
            (csk,),
        ).fetchone()[0]
        assert sel == rev  # higher quality wins
        conn.commit()
    finally:
        conn.close()


def test_calendar_and_contact_same_key(disposable_db: Path) -> None:
    conn = sqlite3.connect(str(disposable_db))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        src = source_locator_hash("iCloud")
        cal = calendar_locator_hash(src, "cal1")
        local = event_local_id_hash(cal, "ek1")
        occ = occurrence_key(cal, ical_uid="UID1", ek_event_id="ek1", start_utc="2026-07-29T15:00:00Z")
        ph = calendar_payload_hash(
            subject="M", body_text=None, body_html=None, body_preview=None,
            start_datetime_utc="2026-07-29T15:00:00Z", end_datetime_utc="2026-07-29T16:00:00Z",
            location_display=None,
        )
        rev = calendar_revision_key(occ, ph)
        snap = calendar_raw_snapshot_id(rev)
        raw = CalendarRawFields(
            raw_calendar_event_id=snap,
            graph_event_id_hash=apple_absent_graph_event_id_hash(local),
            subject="M",
            start_datetime_utc="2026-07-29T15:00:00Z",
            end_datetime_utc="2026-07-29T16:00:00Z",
            source_quality="apple_eventkit_full",
            payload_hash=ph,
            join_url_policy="local_db_only",
            raw_sidecar_json=json.dumps({"graph_id_absent": True}),
        )
        obs = CalendarObservationFields(
            observation_id="cobs1",
            source_locator_hash=src,
            calendar_locator_hash=cal,
            source_local_id_hash=local,
        )
        import_calendar_observation_and_revision(
            conn,
            observation_fields=obs,
            revision_key=rev,
            occurrence_key=occ,
            payload_hash=ph,
            raw_calendar=raw,
            source_quality="apple_eventkit_full",
            provider="apple_eventkit",
            observed_at_utc="2026-07-29T12:00:00Z",
        )
        # contact
        cont = container_locator_hash("iCloud")
        cid = contact_id_hash(cont, "CN-1")
        ent = contact_entity_id(cont, cid)
        payload = json.dumps({"n": "Ada"})
        cph = contact_payload_hash(payload)
        crev = contact_revision_key(ent, cph)
        csnap = contact_raw_snapshot_id(crev)
        craw = ContactRawFields(
            raw_contact_payload_id=csnap,
            contact_entity_id=ent,
            structured_payload_json=payload,
            payload_hash=cph,
            source_quality="cncontact_full",
            created_utc="2026-07-29T12:00:00Z",
        )
        cobs = ContactObservationFields(
            observation_id="ctobs1",
            container_locator_hash=cont,
            contact_id_hash=cid,
        )
        import_contact_observation_and_revision(
            conn,
            observation_fields=cobs,
            revision_key=crev,
            contact_entity_id=ent,
            payload_hash=cph,
            raw_contact=craw,
            source_quality="cncontact_full",
            provider="cncontact_icloud",
            observed_at_utc="2026-07-29T12:00:00Z",
        )
        conn.commit()
    finally:
        conn.close()


import pytest
from pathlib import Path
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

@pytest.fixture
def disposable_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HB_DB_STORAGE_GUARD", "permissive")
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    db = tmp_path / "rehearsal.sqlite"
    ver = SQLiteMigrator(db_path=str(db)).apply()
    assert int(ver) == LATEST_SCHEMA_VERSION
    return db

