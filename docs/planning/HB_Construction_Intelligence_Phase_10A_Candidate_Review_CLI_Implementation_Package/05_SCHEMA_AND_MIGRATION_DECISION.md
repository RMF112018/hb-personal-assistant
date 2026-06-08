# 05 Schema and Migration Decision

## Decision

Use a small additive V43 migration for the full workflow.

## Why migration is recommended

The current schema is enough for basic list/show/status update, but not enough for a durable snooze/edit workflow with auditability. The requested workflow includes snooze metadata, review notes, reviewer metadata, and edit audit events.

## V43 candidate table additions

Add nullable fields to both `task_candidates` and `commitment_candidates`:

```sql
snoozed_until_utc TEXT;
reviewed_utc TEXT;
reviewed_by TEXT;
review_note_redacted TEXT;
```

## V43 review event additions

Add nullable fields to `candidate_review_events`:

```sql
changes_json_redacted TEXT;
snoozed_until_utc TEXT;
reviewer_ref TEXT;
```

## Required existing drift fix

Fix the store method that inserts `candidate_review_events`. The observed V41 DDL uses:

```text
review_event_id, candidate_type, candidate_id, action, prior_status, new_status, user_note_redacted, created_utc
```

Do not insert using non-existent columns such as `event_id`, `decision`, or `reason_redacted` unless the migration intentionally introduces them. Prefer matching the existing DDL and adding only the V43 nullable fields above.

## Migration constraints

- Additive only.
- No data deletion.
- No rewrite of existing candidate IDs or stable keys.
- No source ref mutation.
- Existing no-raw/no-writeback columns remain unchanged and default zero.
- Migration must be covered by schema tests.
