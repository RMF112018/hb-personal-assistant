# 01 — Schema & Read-Model Audit

Validated on a `/tmp` copy of the plain prod DB (schema V49, integrity_check = ok).

## Substrate present (real data, copy)

| Table | Rows |
|---|---:|
| email_message_raw_content | 20645 |
| email_raw_message_structured | 405 |
| email_raw_thread_structured | 223 |
| task_candidates | 0 |
| commitment_candidates | 0 |
| daily_brief_action_candidates | 0 |

Follow-up layers empty with structured email present → the honest *data-gap* state.

## Safe structured fields used (no raw body)

message_id_hash, conversation_id_hash, thread_ref, project_key, subject, from_name, from_address,
sent_at_utc, received_at_utc, recipient_count, attachment_count, has_attachments, body **availability
flags + char counts**, source_quality, thread message_count / participant_count / thread_subject.

## Unsafe fields avoided

body_text, body_html, body_preview, raw recipient/attendee arrays, join_url, any URL/token. Raw body
access (`load_body`) is NOT used in this pass; `raw_content_access_events` is unchanged by extraction.

## Schema decision

**No migration.** task_candidates / commitment_candidates (PK candidate_id + UNIQUE stable_key),
daily_brief_action_candidates + candidate_source_refs (deterministic ids via the central writer) all
support deterministic, idempotent candidate + source-ref persistence already.
