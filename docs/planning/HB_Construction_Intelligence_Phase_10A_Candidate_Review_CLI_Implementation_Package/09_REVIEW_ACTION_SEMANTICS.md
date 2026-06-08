# 09 Review Action Semantics

## Accept

`review accept` updates `review_status` to `accepted`, sets review metadata, and writes a review event.

It must not perform external writeback or create a task in any external system.

## Ignore

`review ignore` updates stored status to `suppressed`. It should accept `--reason`, store it only as redacted/safe text, and write a review event.

## Reject

`review reject` updates stored status to `rejected`. It should be used for incorrect extraction, wrong classification, or invalid candidate content.

## Snooze

`review snooze` updates stored status to `snoozed`, sets `snoozed_until_utc`, and writes a review event.

Default pending list should hide snoozed candidates until due. Recommended behavior: default pending list includes pending only; `summary` shows due snoozed count separately.

## Edit

`review edit` updates allowed redacted/local candidate fields only. It must write `changes_json_redacted` to the event table. The event should capture old and new values for changed fields, with values restricted to safe candidate metadata.

## Batch

Batch review commands should default to dry-run and require `--apply`. Include `--max-actions` to prevent accidental large updates.
