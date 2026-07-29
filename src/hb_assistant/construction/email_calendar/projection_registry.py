"""Email/calendar projection registry: the single source of truth that drives the V49
structured projection schema parity check, the projection engine, and the completeness
matrix.

Unlike the Procore registry (which is generated from a generic ``payload_json`` blob
inventory), email/calendar raw content is already stored in *typed columns* plus a small
set of JSON columns. So this registry is an explicit, hand-authored **allow-list** that
maps, per source family:

- every business scalar column on the raw table -> a structured destination column (or a
  body-availability flag for body columns, which stay local-private in the raw table),
- every nested JSON array of objects -> a child/detail table with an item field map,
- every nested JSON object / scalar-array / lossless remainder -> a declared lossless
  sidecar column on the structured row,
- every system/provenance column -> an explicit exclusion with a reason, and
- any policy-blocked value (the calendar join URL) -> an explicit exclusion with a reason.

It is an allow-list, not a wildcard: a JSON key observed in a raw row that is absent from
the registry is ``unmapped`` and makes the completeness matrix fail / the reprocess path
fail closed. ``lossless_sidecar`` JSON columns are inherently covered (their entire content
is preserved verbatim), so only *array-of-object* and *named-object* JSON columns carry a
declared key allow-list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REGISTRY_VERSION = 1
PROJECTION_SCHEMA_VERSION = "email_calendar_projection_v1"

# Destination kinds (mirror the package's allowed destinations).
PRIMARY_COLUMN = "primary_column"
CHILD_TABLE_COLUMN = "child_table_column"
LOSSLESS_SIDECAR = "lossless_sidecar_json"
EXCLUDED_NON_BUSINESS = "excluded_non_business"
EXCLUDED_TRANSPORT_SECRET = "excluded_transport_secret"
EXCLUDED_POLICY_BLOCKED = "excluded_policy_blocked"


@dataclass(frozen=True)
class ScalarField:
    """A business scalar raw column projected to a structured primary column."""

    raw_column: str
    dest_column: str
    business_category: str


@dataclass(frozen=True)
class BodyField:
    """A body column that stays local-private in the raw table; the structured row carries
    only a queryable availability flag + char length (linked back via ``raw_row_id``)."""

    raw_column: str
    available_column: str
    chars_column: str
    business_category: str = "message_body"


@dataclass(frozen=True)
class ExcludedField:
    """A raw column intentionally NOT projected as a business field, with a reason."""

    raw_column: str
    dest_kind: str  # EXCLUDED_NON_BUSINESS | EXCLUDED_TRANSPORT_SECRET | EXCLUDED_POLICY_BLOCKED
    reason: str


@dataclass(frozen=True)
class ChildArray:
    """A nested array-of-objects extracted into a child/detail table."""

    source_json_column: str  # raw JSON column holding (or containing) the array
    source_path: str | None  # key path inside the column, or None if the column *is* the array
    array_path: str  # logical inventory path, e.g. "to_recipients_json[]"
    child_table: str
    role: str | None  # fixed role tag for the rows (recipients: to/cc/bcc), else None
    item_fields: tuple[tuple[str, str], ...]  # (json_key, dest_column)
    body_item_fields: tuple[BodyField, ...]  # item body keys -> availability flag columns
    declared_item_keys: frozenset[str]
    excluded_item_keys: frozenset[str]


@dataclass(frozen=True)
class SidecarColumn:
    """A JSON column preserved losslessly inside the structured row's sidecar. Its entire
    content is covered by definition, so it carries no per-key allow-list."""

    source_json_column: str
    dest_sidecar_column: str
    reason: str


@dataclass(frozen=True)
class SourceFamilyPlan:
    family: str
    raw_table: str
    raw_pk: str
    structured_table: str
    identity_fields: tuple[ScalarField, ...]
    scalar_fields: tuple[ScalarField, ...]
    body_fields: tuple[BodyField, ...]
    excluded_columns: tuple[ExcludedField, ...]
    child_arrays: tuple[ChildArray, ...]
    sidecar_columns: tuple[SidecarColumn, ...]
    derived_columns: tuple[str, ...] = field(default_factory=tuple)

    # --- helpers ---------------------------------------------------------------
    def business_raw_columns(self) -> frozenset[str]:
        """Raw columns considered *business* for the completeness gate (everything that is
        not an explicit system/provenance/policy exclusion and not the primary key)."""
        excluded = {self.raw_pk} | {e.raw_column for e in self.excluded_columns}
        return frozenset(excluded)

    def mapped_scalar_columns(self) -> frozenset[str]:
        cols = {f.raw_column for f in self.identity_fields}
        cols |= {f.raw_column for f in self.scalar_fields}
        cols |= {f.raw_column for f in self.body_fields}
        cols |= {c.source_json_column for c in self.child_arrays if c.source_path is None}
        cols |= {s.source_json_column for s in self.sidecar_columns}
        # child arrays / sidecars nested inside a json column also "consume" that column
        cols |= {c.source_json_column for c in self.child_arrays}
        return frozenset(cols)

    def required_structured_columns(self) -> list[str]:
        out: list[str] = [f.dest_column for f in self.identity_fields]
        out += [f.dest_column for f in self.scalar_fields]
        for b in self.body_fields:
            out += [b.available_column, b.chars_column]
        out += [s.dest_sidecar_column for s in self.sidecar_columns]
        out += list(self.derived_columns)
        return out

    def required_child_columns(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for c in self.child_arrays:
            cols = [dest for _, dest in c.item_fields]
            cols += [b.available_column for b in c.body_item_fields]
            cols += [b.chars_column for b in c.body_item_fields]
            out.setdefault(c.child_table, [])
            for col in cols:
                if col not in out[c.child_table]:
                    out[c.child_table].append(col)
        return out


# --- The committed registry -------------------------------------------------------

_EMAIL_MESSAGE = SourceFamilyPlan(
    family="email_message",
    raw_table="email_message_raw_content",
    raw_pk="raw_email_id",
    structured_table="email_raw_message_structured",
    identity_fields=(
        ScalarField("message_id_hash", "message_id_hash", "identifier"),
        ScalarField("internet_message_id_hash", "internet_message_id_hash", "identifier"),
        ScalarField("conversation_id_hash", "conversation_id_hash", "identifier"),
        ScalarField("source_ref_hash", "source_ref_hash", "source_ref"),
        ScalarField("project_key", "project_key", "project_ref"),
    ),
    scalar_fields=(
        ScalarField("subject", "subject", "subject"),
        ScalarField("from_name", "from_name", "sender"),
        ScalarField("from_address", "from_address", "sender"),
        ScalarField("sent_at_utc", "sent_at_utc", "timestamp"),
        ScalarField("received_at_utc", "received_at_utc", "timestamp"),
        ScalarField("has_attachments", "has_attachments", "attachment"),
    ),
    body_fields=(
        BodyField("body_preview", "body_preview_available", "body_preview_chars"),
        BodyField("body_text", "body_text_available", "body_text_chars"),
        BodyField("body_html", "body_html_available", "body_html_chars"),
    ),
    excluded_columns=(
        ExcludedField("created_utc", EXCLUDED_NON_BUSINESS, "system row-create timestamp"),
        ExcludedField("updated_utc", EXCLUDED_NON_BUSINESS, "system row-update timestamp"),
        ExcludedField(
            "source_quality", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "payload_hash", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "raw_capture_run_id", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField("source_record_ref", EXCLUDED_NON_BUSINESS, "provenance linkage column"),
        ExcludedField("source_record_id", EXCLUDED_NON_BUSINESS, "provenance linkage column"),
        ExcludedField(
            "source_updated_at_utc",
            EXCLUDED_NON_BUSINESS,
            "provenance: projected as its own column",
        ),
        ExcludedField(
            "raw_content_schema_version", EXCLUDED_NON_BUSINESS, "provenance schema marker"
        ),
    ),
    child_arrays=(
        ChildArray(
            source_json_column="to_recipients_json",
            source_path=None,
            array_path="to_recipients_json[]",
            child_table="email_raw_message_recipients_structured",
            role="to",
            item_fields=(("name", "name"), ("address", "address")),
            body_item_fields=(),
            declared_item_keys=frozenset({"name", "address", "domain", "type", "role"}),
            excluded_item_keys=frozenset(),
        ),
        ChildArray(
            source_json_column="cc_recipients_json",
            source_path=None,
            array_path="cc_recipients_json[]",
            child_table="email_raw_message_recipients_structured",
            role="cc",
            item_fields=(("name", "name"), ("address", "address")),
            body_item_fields=(),
            declared_item_keys=frozenset({"name", "address", "domain", "type", "role"}),
            excluded_item_keys=frozenset(),
        ),
        ChildArray(
            source_json_column="bcc_recipients_json",
            source_path=None,
            array_path="bcc_recipients_json[]",
            child_table="email_raw_message_recipients_structured",
            role="bcc",
            item_fields=(("name", "name"), ("address", "address")),
            body_item_fields=(),
            declared_item_keys=frozenset({"name", "address", "domain", "type", "role"}),
            excluded_item_keys=frozenset(),
        ),
        ChildArray(
            source_json_column="attachment_metadata_json",
            source_path=None,
            array_path="attachment_metadata_json[]",
            child_table="email_raw_message_attachments_structured",
            role=None,
            item_fields=(
                ("name", "name"),
                ("contentType", "content_type"),
                ("content_type", "content_type"),
                ("size", "size_bytes"),
                ("isInline", "is_inline"),
                ("is_inline", "is_inline"),
                ("id", "attachment_id"),
                ("attachment_id", "attachment_id"),
                ("attachment_id_hash", "attachment_id_hash"),
            ),
            body_item_fields=(),
            declared_item_keys=frozenset(
                {
                    "name",
                    "contentType",
                    "content_type",
                    "size",
                    "isInline",
                    "is_inline",
                    "id",
                    "attachment_id",
                    "attachment_id_hash",
                    "lastModifiedDateTime",
                    "has_attachments",  # current indexer stub key
                    "contentId",
                    "sensitivity_hint",
                }
            ),
            excluded_item_keys=frozenset(),
        ),
    ),
    sidecar_columns=(
        SidecarColumn(
            "raw_sidecar_json",
            "payload_sidecar_json",
            "lossless remainder of widened Graph message fields without dedicated columns",
        ),
    ),
    derived_columns=(
        "thread_ref",
        "recipient_count",
        "attachment_count",
        "raw_email_id",
        "source_quality",
        "payload_hash",
        "raw_capture_run_id",
        "source_updated_at_utc",
    ),
)

_EMAIL_THREAD = SourceFamilyPlan(
    family="email_thread",
    raw_table="email_thread_raw_context",
    raw_pk="raw_thread_context_id",
    structured_table="email_raw_thread_structured",
    identity_fields=(
        ScalarField("thread_ref", "thread_ref", "identifier"),
        ScalarField("conversation_id_hash", "conversation_id_hash", "identifier"),
        ScalarField("project_key", "project_key", "project_ref"),
    ),
    scalar_fields=(
        ScalarField("thread_subject", "thread_subject", "subject"),
        ScalarField("message_count", "message_count", "rollup"),
        ScalarField("participant_count", "participant_count", "rollup"),
        ScalarField("model_ready", "model_ready", "flag"),
    ),
    body_fields=(),
    excluded_columns=(
        ExcludedField("created_utc", EXCLUDED_NON_BUSINESS, "system row-create timestamp"),
        ExcludedField("updated_utc", EXCLUDED_NON_BUSINESS, "system row-update timestamp"),
        ExcludedField(
            "source_quality", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "payload_hash", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "raw_capture_run_id", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "raw_content_schema_version", EXCLUDED_NON_BUSINESS, "provenance schema marker"
        ),
    ),
    child_arrays=(
        ChildArray(
            source_json_column="messages_json",
            source_path=None,
            array_path="messages_json[]",
            child_table="email_raw_thread_messages_structured",
            role=None,
            item_fields=(
                ("subject", "subject"),
                ("from_name", "from_name"),
                ("from_address", "from_address"),
                ("received_at", "message_received_at"),
            ),
            body_item_fields=(
                BodyField("body_text", "body_text_available", "body_text_chars"),
                BodyField("body_html", "body_html_available", "body_html_chars"),
            ),
            declared_item_keys=frozenset(
                {
                    "subject",
                    "from_name",
                    "from_address",
                    "received_at",
                    "body_text",
                    "body_html",
                    "message_id_hash",
                    "sent_at",
                }
            ),
            excluded_item_keys=frozenset(),
        ),
    ),
    sidecar_columns=(
        SidecarColumn(
            "source_refs_json",
            "source_refs_sidecar_json",
            "lossless source-ref array (scalar array preserved verbatim)",
        ),
    ),
    derived_columns=(
        "has_full_body",
        "raw_thread_context_id",
        "source_quality",
        "payload_hash",
        "raw_capture_run_id",
    ),
)

_CALENDAR_EVENT = SourceFamilyPlan(
    family="calendar_event",
    raw_table="calendar_event_raw_content",
    raw_pk="raw_calendar_event_id",
    structured_table="calendar_raw_event_structured",
    identity_fields=(
        ScalarField("graph_event_id_hash", "graph_event_id_hash", "identifier"),
        ScalarField("event_index_id", "event_index_id", "identifier"),
        ScalarField("source_ref_hash", "source_ref_hash", "source_ref"),
        ScalarField("project_key", "project_key", "project_ref"),
    ),
    scalar_fields=(
        ScalarField("subject", "subject", "subject"),
        ScalarField("location_display", "location_display", "location"),
        ScalarField("organizer_name", "organizer_name", "organizer"),
        ScalarField("organizer_email", "organizer_email", "organizer"),
        ScalarField("online_meeting_provider", "online_meeting_provider", "online_meeting"),
        ScalarField("start_datetime_utc", "start_datetime_utc", "timestamp"),
        ScalarField("end_datetime_utc", "end_datetime_utc", "timestamp"),
    ),
    body_fields=(
        BodyField("body_preview", "body_preview_available", "body_preview_chars"),
        BodyField("body_text", "body_text_available", "body_text_chars"),
        BodyField("body_html", "body_html_available", "body_html_chars"),
    ),
    excluded_columns=(
        ExcludedField(
            "join_url",
            EXCLUDED_POLICY_BLOCKED,
            "join URL retained only in the raw table under join_url_policy=local_db_only; "
            "the structured row carries a has_join_url flag, never the URL value",
        ),
        ExcludedField("join_url_policy", EXCLUDED_NON_BUSINESS, "system policy marker column"),
        ExcludedField("created_utc", EXCLUDED_NON_BUSINESS, "system row-create timestamp"),
        ExcludedField("updated_utc", EXCLUDED_NON_BUSINESS, "system row-update timestamp"),
        ExcludedField(
            "source_quality", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "payload_hash", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField(
            "raw_capture_run_id", EXCLUDED_NON_BUSINESS, "provenance: projected as its own column"
        ),
        ExcludedField("source_record_ref", EXCLUDED_NON_BUSINESS, "provenance linkage column"),
        ExcludedField("source_record_id", EXCLUDED_NON_BUSINESS, "provenance linkage column"),
        ExcludedField(
            "source_updated_at_utc",
            EXCLUDED_NON_BUSINESS,
            "provenance: projected as its own column",
        ),
        ExcludedField(
            "raw_content_schema_version", EXCLUDED_NON_BUSINESS, "provenance schema marker"
        ),
    ),
    child_arrays=(
        ChildArray(
            source_json_column="attendees_json",
            source_path=None,
            array_path="attendees_json[]",
            child_table="calendar_raw_event_attendees_structured",
            role=None,
            item_fields=(
                ("type", "attendee_type"),
                ("status", "response_status"),
                ("name", "name"),
                ("address", "address"),
            ),
            body_item_fields=(),
            declared_item_keys=frozenset(
                {"type", "status", "name", "address", "domain", "emailAddress", "responseStatus"}
            ),
            excluded_item_keys=frozenset(),
        ),
        ChildArray(
            source_json_column="recurrence_json",
            source_path=None,
            array_path="recurrence_json",  # single object modelled as 0/1 child rows
            child_table="calendar_raw_event_recurrence_structured",
            role=None,
            item_fields=(
                ("pattern.type", "pattern_type"),
                ("pattern.interval", "pattern_interval"),
                ("range.type", "range_type"),
                ("range.startDate", "range_start"),
                ("range.endDate", "range_end"),
                ("range.numberOfOccurrences", "number_of_occurrences"),
                ("range.recurrenceTimeZone", "recurrence_timezone"),
            ),
            body_item_fields=(),
            declared_item_keys=frozenset(
                {
                    "pattern",
                    "pattern.type",
                    "pattern.interval",
                    "pattern.month",
                    "pattern.dayOfMonth",
                    "pattern.daysOfWeek",
                    "pattern.firstDayOfWeek",
                    "pattern.index",
                    "range",
                    "range.type",
                    "range.startDate",
                    "range.endDate",
                    "range.numberOfOccurrences",
                    "range.recurrenceTimeZone",
                }
            ),
            excluded_item_keys=frozenset(),
        ),
        ChildArray(
            source_json_column="raw_sidecar_json",
            source_path="locations",
            array_path="raw_sidecar_json.locations[]",
            child_table="calendar_raw_event_locations_structured",
            role=None,
            item_fields=(
                ("displayName", "display_name"),
                ("locationType", "location_type"),
                ("locationUri", "location_uri"),
                ("address.street", "address_street"),
                ("address.city", "address_city"),
                ("address.state", "address_state"),
                ("address.countryOrRegion", "address_country_or_region"),
                ("address.postalCode", "address_postal_code"),
                ("coordinates.latitude", "coordinates_latitude"),
                ("coordinates.longitude", "coordinates_longitude"),
            ),
            body_item_fields=(),
            declared_item_keys=frozenset(
                {
                    "displayName",
                    "locationType",
                    "locationUri",
                    "uniqueId",
                    "uniqueIdType",
                    "address",
                    "address.street",
                    "address.city",
                    "address.state",
                    "address.countryOrRegion",
                    "address.postalCode",
                    "coordinates",
                    "coordinates.latitude",
                    "coordinates.longitude",
                }
            ),
            excluded_item_keys=frozenset(),
        ),
    ),
    sidecar_columns=(
        SidecarColumn(
            "raw_sidecar_json",
            "payload_sidecar_json",
            "lossless remainder of widened Graph event fields (isAllDay, categories, "
            "created/lastModified, originalStart, showAs, type, seriesMasterId, "
            "onlineMeeting minus joinUrl) without dedicated columns",
        ),
        SidecarColumn(
            "recurrence_json",
            "recurrence_sidecar_json",
            "lossless full recurrence object (every recurrence path preserved verbatim)",
        ),
    ),
    derived_columns=(
        "has_join_url",
        "join_url_policy",
        "attendee_count",
        "has_recurrence",
        "raw_calendar_event_id",
        "source_quality",
        "payload_hash",
        "raw_capture_run_id",
        "source_updated_at_utc",
    ),
)

PLANS: dict[str, SourceFamilyPlan] = {
    _EMAIL_MESSAGE.family: _EMAIL_MESSAGE,
    _EMAIL_THREAD.family: _EMAIL_THREAD,
    _CALENDAR_EVENT.family: _CALENDAR_EVENT,
}

SOURCE_FAMILIES = tuple(PLANS.keys())


def plan_for(family: str) -> SourceFamilyPlan | None:
    return PLANS.get(family)


def plan_for_raw_table(raw_table: str) -> SourceFamilyPlan | None:
    for plan in PLANS.values():
        if plan.raw_table == raw_table:
            return plan
    return None


def all_structured_tables() -> list[str]:
    tables: list[str] = []
    for plan in PLANS.values():
        tables.append(plan.structured_table)
        for child in plan.child_arrays:
            if child.child_table not in tables:
                tables.append(child.child_table)
    return tables


__all__ = [
    "CHILD_TABLE_COLUMN",
    "EXCLUDED_NON_BUSINESS",
    "EXCLUDED_POLICY_BLOCKED",
    "EXCLUDED_TRANSPORT_SECRET",
    "LOSSLESS_SIDECAR",
    "PLANS",
    "PRIMARY_COLUMN",
    "PROJECTION_SCHEMA_VERSION",
    "REGISTRY_VERSION",
    "SOURCE_FAMILIES",
    "BodyField",
    "ChildArray",
    "ExcludedField",
    "ScalarField",
    "SidecarColumn",
    "SourceFamilyPlan",
    "all_structured_tables",
    "plan_for",
    "plan_for_raw_table",
]

# Apple MCC projections ride the same completeness harness via contact registry.
