"""Typed raw field bags for email / calendar / contact snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EmailRawFields:
    raw_email_id: str
    message_id_hash: str
    internet_message_id_hash: str | None = None
    conversation_id_hash: str | None = None
    source_ref_hash: str | None = None
    project_key: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    from_name: str | None = None
    from_address: str | None = None
    to_recipients_json: str = "[]"
    cc_recipients_json: str = "[]"
    bcc_recipients_json: str = "[]"
    sent_at_utc: str | None = None
    received_at_utc: str | None = None
    has_attachments: int = 0
    attachment_metadata_json: str = "[]"
    source_quality: str = "metadata_only"
    payload_hash: str = ""
    raw_capture_run_id: str | None = None
    source_record_ref: str | None = None
    source_record_id: int | None = None
    source_updated_at_utc: str | None = None
    raw_content_schema_version: str = "email_raw_v1"
    raw_sidecar_json: str | None = None

    def as_insert_tuple(self) -> tuple[Any, ...]:
        return (
            self.raw_email_id,
            self.message_id_hash,
            self.internet_message_id_hash,
            self.conversation_id_hash,
            self.source_ref_hash,
            self.project_key,
            self.subject,
            self.body_preview,
            self.body_text,
            self.body_html,
            self.from_name,
            self.from_address,
            self.to_recipients_json,
            self.cc_recipients_json,
            self.bcc_recipients_json,
            self.sent_at_utc,
            self.received_at_utc,
            self.has_attachments,
            self.attachment_metadata_json,
            self.source_quality,
            self.payload_hash,
            self.raw_capture_run_id,
            self.source_record_ref,
            self.source_record_id,
            self.source_updated_at_utc,
            self.raw_content_schema_version,
            self.raw_sidecar_json,
        )


@dataclass
class CalendarRawFields:
    raw_calendar_event_id: str
    event_index_id: str | None = None
    graph_event_id_hash: str = ""
    source_ref_hash: str | None = None
    project_key: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    location_display: str | None = None
    organizer_name: str | None = None
    organizer_email: str | None = None
    attendees_json: str = "[]"
    online_meeting_provider: str | None = None
    join_url: str | None = None
    recurrence_json: str | None = None
    start_datetime_utc: str | None = None
    end_datetime_utc: str | None = None
    source_quality: str = "metadata_only"
    payload_hash: str = ""
    raw_capture_run_id: str | None = None
    source_record_ref: str | None = None
    source_record_id: int | None = None
    source_updated_at_utc: str | None = None
    raw_content_schema_version: str = "calendar_raw_v1"
    join_url_policy: str | None = None
    raw_sidecar_json: str | None = None

    def as_insert_tuple(self) -> tuple[Any, ...]:
        return (
            self.raw_calendar_event_id,
            self.event_index_id,
            self.graph_event_id_hash,
            self.source_ref_hash,
            self.project_key,
            self.subject,
            self.body_preview,
            self.body_text,
            self.body_html,
            self.location_display,
            self.organizer_name,
            self.organizer_email,
            self.attendees_json,
            self.online_meeting_provider,
            self.join_url,
            self.recurrence_json,
            self.start_datetime_utc,
            self.end_datetime_utc,
            self.source_quality,
            self.payload_hash,
            self.raw_capture_run_id,
            self.source_record_ref,
            self.source_record_id,
            self.source_updated_at_utc,
            self.raw_content_schema_version,
            self.join_url_policy,
            self.raw_sidecar_json,
        )


@dataclass
class ContactRawFields:
    raw_contact_payload_id: str
    contact_entity_id: str
    structured_payload_json: str
    payload_hash: str
    schema_version: str = "apple_contact_raw_v1"
    source_quality: str = "cncontact_full"
    created_utc: str = ""

    def as_insert_tuple(self) -> tuple[Any, ...]:
        return (
            self.raw_contact_payload_id,
            self.contact_entity_id,
            self.structured_payload_json,
            self.payload_hash,
            self.schema_version,
            self.source_quality,
            self.created_utc,
        )


@dataclass
class EmailObservationFields:
    observation_id: str
    account_locator_hash: str
    source_local_id_hash: str
    mailbox_locator_hash: str | None = None
    graph_id_hash: str | None = None
    raw_source_sha256: str | None = None
    raw_source_bytes: int | None = None
    fidelity_class: str | None = None
    parser_version: str = "mail_parser_v1"
    adapter_version: str = "apple_mail_adapter_v1"
    spool_item_id: str | None = None
    capture_run_id: str | None = None
    raw_sidecar_json: str | None = None
    import_status: str = "successful"
    # Human-readable source locators (V135); hashes remain identity keys.
    source_account: str = ""
    source_scope: str | None = None


@dataclass
class CalendarObservationFields:
    observation_id: str
    source_locator_hash: str
    calendar_locator_hash: str
    source_local_id_hash: str
    graph_id_hash: str | None = None
    ical_uid_hash: str | None = None
    ics_provenance: str = "none"
    raw_ics_sha256: str | None = None
    raw_ics_bytes: int | None = None
    parser_version: str = "cal_parser_v1"
    adapter_version: str = "apple_eventkit_adapter_v1"
    spool_item_id: str | None = None
    capture_run_id: str | None = None
    raw_sidecar_json: str | None = None
    import_status: str = "successful"
    # EventKit source title + calendar title (V135).
    source_account: str = ""
    source_scope: str | None = None


@dataclass
class ContactObservationFields:
    observation_id: str
    container_locator_hash: str
    contact_id_hash: str
    adapter_version: str = "cncontact_adapter_v1"
    spool_item_id: str | None = None
    capture_run_id: str | None = None
    raw_sidecar_json: str | None = None
    import_status: str = "successful"
    # CN container display name (V135).
    source_account: str = ""
    source_scope: str | None = None
