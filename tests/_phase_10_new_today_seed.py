"""Shared synthetic fixture seeder for the Phase 10 (252) New Today digest tests.

Seeds one in-window row per source family (email + actionable follow-up, calendar upcoming, Procore
RFI / RFI-response / invoice / change-order / commitment, SharePoint file) plus detail-missing rows
that must demote to diagnostics. All data is synthetic (no real names/content), so rendered samples
are safe to commit as evidence. Foreign keys are disabled for the seed; the real pipeline populates
parent rows.
"""

from __future__ import annotations

from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator

#: A timestamp inside the deterministic fallback refresh window for brief_date 2026-06-12.
IN_WINDOW = "2026-06-11T20:30:00+00:00"
BRIEF_DATE = "2026-06-12"


def seed_new_today_fixture(db_path: str, *, include_detail_gaps: bool = True) -> None:
    """Apply migrations and seed the synthetic New Today substrate into ``db_path``."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    meta: dict[str, list] = {}

    def _cols(table: str) -> list:
        if table not in meta:
            meta[table] = [
                (r[1], r[2], r[3], r[4]) for r in conn.execute(f"PRAGMA table_info({table})")
            ]
        return meta[table]

    def ins(table: str, **kw: object) -> None:
        for name, typ, notnull, dflt in _cols(table):
            if notnull and dflt is None and name not in kw:
                kw[name] = 0 if str(typ or "").upper().startswith(("INT", "REAL", "NUM")) else "x"
        cols = ",".join(kw)
        conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(kw))})", tuple(kw.values())
        )

    # Email: an in-window message + an actionable (waiting_on_me) follow-up derived this cycle.
    ins(
        "email_raw_message_structured",
        projection_id="m1",
        message_id_hash="h1",
        subject="status of the Alton Hilltop contract",
        from_name="John Smith",
        from_address="jsmith@coastal-pipeline.com",
        received_at_utc=IN_WINDOW,
        project_key="alton-hilltop-pbg",
        is_current=1,
    )
    ins(
        "task_candidates",
        candidate_id="t1",
        stable_key="tk1",
        title_redacted="Alton Hilltop contract status",
        project_key="alton-hilltop-pbg",
        waiting_state="waiting_on_me",
        urgency="high",
        reason_redacted="They asked whether the latest draft has been returned.",
        recommended_next_action="Confirm whether the latest draft has been returned or assign follow-up.",
        created_utc=IN_WINDOW,
    )

    # Calendar: an upcoming meeting in the look-ahead window.
    ins(
        "calendar_raw_event_structured",
        projection_id="c1",
        event_index_id="e1",
        subject="Alton Hilltop vibro compaction",
        organizer_name="Brian Olsen",
        online_meeting_provider="teamsForBusiness",
        start_datetime_utc="2026-06-18T17:30:00+00:00",
        end_datetime_utc="2026-06-18T18:30:00+00:00",
        project_key="alton-hilltop-pbg",
        attendee_count=10,
        is_current=1,
    )

    # Procore RFI (open, cost impact, ball in court) + an RFI response.
    ins(
        "procore_ep_rfis",
        record_key="rk1",
        record_id="525",
        project_key="tropical",
        number="025",
        full_number="025",
        subject="Tropical drainage detail",
        status="open",
        translated_status="Open",
        ball_in_court_name="Seema Shibi",
        cost_impact_status="Yes",
        updated_at=IN_WINDOW,
        payload_seen_first_utc=IN_WINDOW,
        is_current=1,
    )
    ins(
        "procore_raw_rfi_responses",
        record_key="rr1",
        record_id="900",
        project_key="tropical",
        record_number="025",
        status="Closed",
        responsible_party_name="Seema Shibi",
        source_updated_at_utc=IN_WINDOW,
        payload_seen_first_utc=IN_WINDOW,
        is_current=1,
    )

    # Procore subcontractor invoice (vendor/number/amount/period/status; not yet reviewed).
    ins(
        "procore_ep_subcontractor_invoices",
        record_key="ik1",
        record_id="1842",
        project_key="tropical",
        invoice_number="1842",
        vendor_name="Coastal Pipeline",
        status="Submitted",
        requisition_end="2026-05-25",
        summary_current_payment_due="58200.00",
        updated_at=IN_WINDOW,
        payload_seen_first_utc=IN_WINDOW,
        is_current=1,
    )

    # Procore commitment change order + commitment contract.
    ins(
        "procore_ep_commitment_change_orders",
        record_key="cok1",
        record_id="77",
        project_key="pga-modern-garage",
        number="07",
        title="Garage slab revision",
        status="Pending",
        grand_total="12500",
        created_by_name="Dana Lee",
        updated_at=IN_WINDOW,
        payload_seen_first_utc=IN_WINDOW,
        is_current=1,
    )
    ins(
        "procore_ep_commitment_contracts",
        record_key="cmk1",
        record_id="300",
        project_key="the-wellington",
        number="C-12",
        title="Site concrete",
        status="Approved",
        grand_total="480000",
        updated_at=IN_WINDOW,
        payload_seen_first_utc=IN_WINDOW,
        is_current=1,
    )

    # SharePoint / OneDrive file metadata change.
    ins(
        "construction_drive_items",
        source_id="s1",
        drive_id="d1",
        drive_item_id="f1",
        name="Wellington Permit Set Rev3.pdf",
        is_file=1,
        deleted=0,
        last_modified_datetime=IN_WINDOW,
        last_modified_by_display_name="Maria Gomez",
        project_key="the-wellington",
        document_type_detected="Permit Set",
    )

    if include_detail_gaps:
        # Detail-missing Procore rows that MUST demote to diagnostics (no number/status), never
        # rendered as a New Today business item.
        ins(
            "procore_ep_rfis",
            record_key="rk2",
            record_id="526",
            project_key="tropical",
            number="",
            full_number="",
            subject="",
            status="",
            translated_status="",
            updated_at=IN_WINDOW,
            payload_seen_first_utc=IN_WINDOW,
            is_current=1,
        )
        ins(
            "procore_ep_subcontractor_invoices",
            record_key="ik2",
            record_id="1843",
            project_key="tropical",
            invoice_number="",
            vendor_name="",
            status="",
            updated_at=IN_WINDOW,
            payload_seen_first_utc=IN_WINDOW,
            is_current=1,
        )

    conn.commit()
