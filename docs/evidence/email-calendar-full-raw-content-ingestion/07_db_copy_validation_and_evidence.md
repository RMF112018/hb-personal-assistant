# 07 — DB-Copy Validation and Evidence

All validation ran against a `/tmp` copy of the production DB. The production DB was never mutated.

## Production DB untouched (Pass 1 + Pass 2)

```text
production DB path:  ~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite
production sha256:   7f04f0b8d69545c65d855295db0a844cc85f6bc5ccfc71c9c09c3e08a211ff4d
unchanged after Pass 1 validation:  TRUE  (sha256 + mtime identical)
unchanged after Pass 2 validation:  TRUE  (sha256 + mtime identical)
```

## /tmp copy projection coverage (real production raw rows)

```text
copy schema head:  48 -> 49 (applied to the COPY only)

surface                      | raw rows | structured rows | unmapped primary | unmapped nested | status
email_message_raw_content    |    1     |      1          |        0         |       0         | complete_with_policy_exclusions
email_thread_raw_context     |    0     |      0          |        0         |       0         | no_raw_rows_available_in_current_copy
calendar_event_raw_content   |  117     |    117          |        0         |       0         | complete_with_policy_exclusions
```

Child rows on the copy: 1262 calendar attendee rows; 2 email recipient/attachment rows.

## /tmp copy consumer source selection (Pass 2)

```text
consumer                        | selects from                     | tier (counts)
email message read model        | email_raw_message_structured     | structured_legacy: 1
calendar event read model       | calendar_raw_event_structured    | structured_legacy: 117
meeting prep                    | calendar_raw_event_structured    | structured (no body/join leak)
model context packets           | structured projection layer      | source_quality_distribution recorded
```

`structured_legacy` reflects the honest `metadata_only` default on pre-V49 production rows; all 118
rows are selected from the **structured layer**, not raw-landing or legacy metadata. After an
operator raw re-ingest, full-body rows reclassify to `structured_full`.

## Validation scope separation

```text
fixture validation:        tests/test_email_calendar_*.py (synthetic full-body rows)
/tmp DB-copy validation:   prod copy at /tmp; coverage + consumer summary; prod sha256/mtime unchanged
production rollout:        operator-controlled; see operator_production_runbook.md (NOT executed here)
```
