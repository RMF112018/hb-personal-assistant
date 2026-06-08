# 11 Snooze, Edit, and Auditability Plan

## Snooze storage

Use `snoozed_until_utc` on candidate tables. Normalize input times to UTC ISO-8601.

Input may be timezone-aware, e.g.:

```bash
--until 2026-06-12T09:00:00-04:00
```

If timezone is missing, fail closed or interpret using repo-standard local timezone if that pattern already exists. Recommended: require timezone-aware input.

## Edit storage

Edits update candidate tables directly for allowed fields, but every edit writes an append-only event.

## Change log format

`changes_json_redacted` should be bounded and shaped like:

```json
{
  "title_redacted": {"from": "Old title", "to": "New title"},
  "assignee_class": {"from": "other", "to": "user"},
  "waiting_state": {"from": "waiting_on_others", "to": "waiting_on_me"}
}
```

All values are already redacted candidate fields. Do not include source raw body text or model prompt/response.
