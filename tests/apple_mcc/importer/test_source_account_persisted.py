"""V135: human-readable source_account is persisted on each observation row."""

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
    calendar_locator_hash,
    calendar_payload_hash,
    calendar_raw_snapshot_id,
    calendar_revision_key,
    event_local_id_hash,
    occurrence_key,
    source_locator_hash,
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
from hb_assistant.apple_mcc.importer.validate import ValidationError, validate_item
from hb_assistant.construction.store.repositories import (
    import_calendar_observation_and_revision,
    import_contact_observation_and_revision,
    import_email_observation_and_revision,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


@pytest.fixture
def disposable_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HB_DB_STORAGE_GUARD", "permissive")
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    db = tmp_path / "rehearsal.sqlite"
    ver = SQLiteMigrator(db_path=str(db)).apply()
    assert int(ver) == LATEST_SCHEMA_VERSION
    return db


def test_mail_calendar_contact_source_account_persisted(disposable_db: Path) -> None:
    conn = sqlite3.connect(str(disposable_db))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        # --- mail ---
        acct = account_locator_hash("BF-Personal")
        mbx = mailbox_locator_hash(acct, "Inbox")
        local = mail_local_id_hash(acct, mbx, "msg-sa")
        csk = canonical_message_key(
            internet_message_id="<sa@example.com>", account_hex=acct, local_id_hex=local
        )
        ph = email_payload_hash(
            subject="S", body_text="b", body_html=None, body_preview=None, to_recipients_json="[]"
        )
        rev = email_revision_key(csk, ph)
        snap = email_raw_snapshot_id(rev)
        import_email_observation_and_revision(
            conn,
            observation_fields=EmailObservationFields(
                observation_id="obs-sa-mail",
                account_locator_hash=acct,
                source_local_id_hash=local,
                mailbox_locator_hash=mbx,
                source_account="BF-Personal",
                source_scope="Inbox",
            ),
            revision_key=rev,
            canonical_message_key=csk,
            payload_hash=ph,
            raw_email=EmailRawFields(
                raw_email_id=snap,
                message_id_hash=local,
                subject="S",
                body_text="b",
                source_quality="apple_mail_full_mime",
                payload_hash=ph,
            ),
            source_quality="apple_mail_full_mime",
            fidelity_class="full_mime",
            provider="apple_mail",
            observed_at_utc="2026-07-30T12:00:00Z",
        )
        row = conn.execute(
            "SELECT source_account, source_scope FROM email_message_source_observations "
            "WHERE observation_id=?",
            ("obs-sa-mail",),
        ).fetchone()
        assert row == ("BF-Personal", "Inbox")

        # --- calendar ---
        src = source_locator_hash("iCloud")
        cal = calendar_locator_hash(src, "cal-sa")
        elocal = event_local_id_hash(cal, "ek-sa")
        occ = occurrence_key(
            cal, ical_uid="UID-SA", ek_event_id="ek-sa", start_utc="2026-07-30T15:00:00Z"
        )
        cph = calendar_payload_hash(
            subject="Meet",
            body_text=None,
            body_html=None,
            body_preview=None,
            start_datetime_utc="2026-07-30T15:00:00Z",
            end_datetime_utc="2026-07-30T16:00:00Z",
            location_display=None,
        )
        crev = calendar_revision_key(occ, cph)
        csnap = calendar_raw_snapshot_id(crev)
        import_calendar_observation_and_revision(
            conn,
            observation_fields=CalendarObservationFields(
                observation_id="obs-sa-cal",
                source_locator_hash=src,
                calendar_locator_hash=cal,
                source_local_id_hash=elocal,
                source_account="iCloud",
                source_scope="Family",
            ),
            revision_key=crev,
            occurrence_key=occ,
            payload_hash=cph,
            raw_calendar=CalendarRawFields(
                raw_calendar_event_id=csnap,
                graph_event_id_hash=apple_absent_graph_event_id_hash(elocal),
                subject="Meet",
                start_datetime_utc="2026-07-30T15:00:00Z",
                end_datetime_utc="2026-07-30T16:00:00Z",
                source_quality="apple_eventkit_full",
                payload_hash=cph,
                join_url_policy="local_db_only",
                raw_sidecar_json=json.dumps({"graph_id_absent": True}),
            ),
            source_quality="apple_eventkit_full",
            provider="apple_eventkit",
            observed_at_utc="2026-07-30T12:00:00Z",
        )
        crow = conn.execute(
            "SELECT source_account, source_scope FROM calendar_event_source_observations "
            "WHERE observation_id=?",
            ("obs-sa-cal",),
        ).fetchone()
        assert crow == ("iCloud", "Family")

        # --- contact ---
        cont = container_locator_hash("iCloud")
        cid = contact_id_hash(cont, "CN-SA")
        ent = contact_entity_id(cont, cid)
        payload = json.dumps({"n": "Ada", "container": "iCloud"}, sort_keys=True)
        tph = contact_payload_hash(payload)
        trev = contact_revision_key(ent, tph)
        tsnap = contact_raw_snapshot_id(trev)
        import_contact_observation_and_revision(
            conn,
            observation_fields=ContactObservationFields(
                observation_id="obs-sa-ct",
                container_locator_hash=cont,
                contact_id_hash=cid,
                source_account="iCloud",
            ),
            revision_key=trev,
            contact_entity_id=ent,
            payload_hash=tph,
            raw_contact=ContactRawFields(
                raw_contact_payload_id=tsnap,
                contact_entity_id=ent,
                structured_payload_json=payload,
                payload_hash=tph,
                source_quality="cncontact_full",
                created_utc="2026-07-30T12:00:00Z",
            ),
            source_quality="cncontact_full",
            provider="cncontact_icloud",
            observed_at_utc="2026-07-30T12:00:00Z",
            contact_type="person",
        )
        trow = conn.execute(
            "SELECT source_account FROM contact_source_observations WHERE observation_id=?",
            ("obs-sa-ct",),
        ).fetchone()
        assert trow == ("iCloud",)
        erow = conn.execute(
            "SELECT source_account FROM contact_entities WHERE contact_entity_id=?",
            (ent,),
        ).fetchone()
        assert erow == ("iCloud",)

        # group-by style proof: distinct source accounts are queryable
        mail_accounts = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT source_account FROM email_message_source_observations"
            )
        }
        assert "BF-Personal" in mail_accounts
        conn.commit()
    finally:
        conn.close()


def test_validate_item_requires_source_account() -> None:
    with pytest.raises(ValidationError, match="source_account_required"):
        validate_item(
            {
                "domain": "calendar",
                "payload_hash": "a" * 64,
                "observed_at_utc": "2026-07-30T12:00:00Z",
                # no source_account / source_title
            }
        )
    validate_item(
        {
            "domain": "calendar",
            "payload_hash": "a" * 64,
            "observed_at_utc": "2026-07-30T12:00:00Z",
            "source_title": "iCloud",
        }
    )
