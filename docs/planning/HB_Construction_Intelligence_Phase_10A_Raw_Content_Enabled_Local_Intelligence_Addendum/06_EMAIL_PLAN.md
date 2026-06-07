# 06 Email Raw Content Plan

## Objective

Enable local raw email ingestion and model extraction.

## Ingestion

Update Graph mail discovery to fetch/store:

- subject;
- bodyPreview;
- body content text;
- body content HTML if available;
- sender/recipient names and addresses;
- sent/received times;
- attachment names/metadata;
- conversation/thread IDs.

## Storage

Persist raw content in `email_message_raw_content`.

## Thread context

Build `email_thread_raw_context` from stored raw message content:

- ordered messages;
- direction;
- actor;
- subject;
- body excerpts;
- attachments;
- project matches;
- source refs.

## Model extraction

Model should receive raw thread packets, not hashed thread summaries.

## Candidate types

- task assigned to user;
- commitment by user;
- commitment by others;
- deadline/due date;
- question needing answer;
- decision needed;
- follow-up needed;
- waiting on me;
- waiting on others;
- meeting prep.
