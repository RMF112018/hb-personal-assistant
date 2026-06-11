# 00 — Repo Truth and Branch Guard

## Repo state at start

```text
branch (intended):  fix/email-calendar-full-raw-content-ingestion  (from main @ 3ad8e694)
main HEAD:          3ad8e69431391cbfe93f4f1205a57909630c93cb
package path:       docs/planning/email_calendar_full_raw_content_ingestion_package/
```

## Schema-head correction (repo truth over package assumption)

The package was authored at schema head **V46** and expected the new migration at **V47**.
Repo truth at execution time: `LATEST_SCHEMA_VERSION = 48` (V47 + V48 were already consumed by
the Procore endpoint-specific projection + column-reconciliation work). The email/calendar
migration was therefore rebased to **V49** (additive, after V48). No destructive change.

## Existing raw-content tables (V42) — preserved, never rewritten

```text
raw_content_policy_state
email_message_raw_content        (raw_email_id PK)
email_thread_raw_context         (raw_thread_context_id PK, UNIQUE thread_ref)
calendar_event_raw_content       (raw_calendar_event_id PK)
raw_content_model_context_packets
raw_content_access_events        (had no writer helper before this work)
```

Columns ABSENT before V49 (added additively): `source_quality`, `raw_capture_run_id`,
`source_record_ref`, `source_record_id`, `source_updated_at_utc`, `payload_hash`,
`raw_content_schema_version`, `join_url_policy` (calendar), `raw_sidecar_json` (email+calendar).

## Concurrent-repo-mutation note

During execution an external process (codex/GitHub Desktop) switched the working tree onto
`codex/scheduled-procore-full-pipeline` and introduced unrelated `docs/evidence/*` working-tree
edits. Those edits are NOT part of this work and were excluded from the commit (only this
package's explicit files were staged). The `fix/...` branch remained at main (3ad8e694).

## Safety posture (Pass 1)

No production DB mutation, no Graph writes, no raw bodies/join-URLs/tokens emitted to evidence.
Validation used a `/tmp` copy only; production DB sha256/mtime proven unchanged (see 04D).
