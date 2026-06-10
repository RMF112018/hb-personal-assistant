# 04A — Raw Field Inventory + Projection Matrix Summary

The mechanical matrix maps every raw scalar column and every nested JSON path observed in the
raw tables to exactly one destination. The committed allow-list lives in
`src/hb_assistant/construction/email_calendar/projection_registry.py`; the full per-path matrix
is `email_calendar_projection_matrix.csv` (this directory; field names/paths + destinations
only — no values).

## Destination kinds used

```text
primary_column          child_table_column        lossless_sidecar_json
excluded_non_business   excluded_policy_blocked    (excluded_transport_secret reserved)
```

## Source families and nested arrays covered

| family | raw table | child / nested destinations |
|---|---|---|
| email_message | email_message_raw_content | to/cc/bcc_recipients_json[] → recipients child (role tag); attachment_metadata_json[] → attachments child; raw_sidecar_json → lossless sidecar |
| email_thread | email_thread_raw_context | messages_json[] → thread-messages child; source_refs_json → lossless sidecar |
| calendar_event | calendar_event_raw_content | attendees_json[] → attendees child; recurrence_json → recurrence child + lossless recurrence sidecar; raw_sidecar_json.locations[] → locations child; raw_sidecar_json → lossless sidecar |

## Documented exclusions (with reasons)

| path | kind | reason |
|---|---|---|
| `calendar_event_raw_content.join_url` | excluded_policy_blocked | join URL retained only in the raw table under `join_url_policy=local_db_only`; the structured row carries a `has_join_url` flag, never the URL value |
| `*.payload_hash`, `*.source_quality`, `*.raw_capture_run_id`, `*.created_utc`, `*.updated_utc`, `*.source_*`, `*.raw_content_schema_version`, `calendar.join_url_policy` | excluded_non_business | system/provenance columns (several are still projected as their own provenance columns) |

## Completeness gate (computed on the `/tmp` production DB copy)

```text
matrix rows:                                          68
unmapped_primary_business_fields  (per family w/ raw): 0
unmapped_nested_business_fields   (per family w/ raw): 0
observed_nested_arrays_without_child_or_sidecar:       0
```

The gate FAILS CLOSED on any undeclared business JSON key: a fixture that injects an unknown
attendee key drives `unmapped_nested_business_fields > 0` and makes enforce-mode reprocess
raise `UnknownProjectionPath` (see `tests/test_email_calendar_projection_completeness.py`).
