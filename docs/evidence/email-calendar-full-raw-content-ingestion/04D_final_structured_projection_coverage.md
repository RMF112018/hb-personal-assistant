# 04D — Final Structured Projection Coverage (Pass 1)

Proof that available raw email/calendar rows are transformed into final structured projections
with zero unmapped business fields. Demonstrated on (a) synthetic fixtures and (b) a `/tmp` copy
of the real production DB. No raw bodies / join URLs / tokens appear in this evidence.

## `/tmp` DB-copy validation (real production raw rows)

```text
production DB sha256 (before & after): 7f04f0b8d69545c65d855295db0a844cc85f6bc5ccfc71c9c09c3e08a211ff4d
production DB unchanged during validation: TRUE   (sha256 + mtime identical)
/tmp copy schema head:  48 -> 49  (migration applied to the COPY only)
```

### Coverage per source family (computed on the copy)

| source_family | raw rows | projected parents | unmapped primary | unmapped nested | status |
|---|---:|---:|---:|---:|---|
| email_message | 1 | 1 | 0 | 0 | complete_with_policy_exclusions |
| email_thread | 0 | 0 | 0 | 0 | no_raw_rows_available_in_current_copy |
| calendar_event | 117 | 117 | 0 | 0 | complete_with_policy_exclusions |

### Structured row counts after reprocess (copy)

```text
email_raw_message_structured                 1
email_raw_message_recipients_structured      1
email_raw_message_attachments_structured     1
calendar_raw_event_structured              117
calendar_raw_event_attendees_structured   1262
calendar_raw_event_recurrence_structured     0   (no recurrence on these rows)
calendar_raw_event_locations_structured      0   (no sidecar locations on pre-V49 rows)
email_raw_thread_*                           0   (no raw thread rows in copy)
```

### Raw-content source-quality distribution (copy)

```text
email_message_raw_content:    {metadata_only: 1}
calendar_event_raw_content:   {metadata_only: 117}
```

> Note: the production raw rows pre-date V49, so `source_quality` carries the additive column
> DEFAULT `metadata_only` (honest — these rows were not (re)captured with full-body
> classification). They still project completely; on the next operator raw-ingest run the
> precedence-aware upsert reclassifies rows that carry a full body to `graph_full_body` /
> `graph_full_event_body`. This is the expected Pass-2/operator-rollout behaviour and is NOT a
> coverage gap.

## Fixture proof (synthetic full-body rows)

`tests/test_email_calendar_structured_projection_remediation.py` proves, with synthetic
graph-full bodies:

- full text & HTML body persist locally; the structured row carries availability flags + char
  lengths + a `raw_row_id` link, and never a duplicated body (`body_text` is not a structured
  column);
- recipients (from + to + cc), attachments, attendees, recurrence (normalised + lossless
  sidecar), locations, and thread messages populate child tables;
- projection is idempotent (re-run yields identical counts);
- source-quality precedence prevents downgrades at both the raw upsert and the projection layer;
- run + coverage receipts are written; a no-raw-rows family is reported honestly.

## Completion gate result

```text
unmapped_primary_business_fields = 0   (every family with raw rows)
unmapped_nested_business_fields  = 0   (every family with raw rows)
observed_nested_arrays_without_child_table_or_mapped_sidecar = 0
projected_parent_rows == raw_parent_rows (except documented no-raw-rows family)
```
