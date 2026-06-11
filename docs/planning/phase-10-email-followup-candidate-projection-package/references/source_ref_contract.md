# Source Ref Contract

## Daily-Brief Source Refs

Every email-derived `daily_brief_action_candidates` row must have one or more `candidate_source_refs` rows.

Use the central writer:

`persist_candidate_with_refs(...)`

Do not hand-roll candidate IDs or source-ref IDs unless repo truth proves the writer cannot support this slice.

## Allowed Source Families

- `email_message`
- `email_thread`
- existing repo names for email/calendar source refs if different

## Allowed Source Tables

- `email_raw_message_structured`
- `email_raw_thread_structured`
- `email_raw_thread_messages_structured`
- raw tables only when structured rows are unavailable and fallback is explicitly documented

## Allowed Ref Values

Use deterministic refs based on hashes/refs:

- `message:{message_id_hash}`
- `thread:{thread_ref}`
- `thread-message:{thread_ref}:{message_id_hash}` if available

The writer hashes source refs before storage.

## Disallowed Ref Values

- raw body refs that reveal local IDs if treated as private
- private URLs
- join URLs
- signed URLs
- Graph URLs
- web links
- tokens
- secrets
- unbounded subjects
- raw body excerpts
