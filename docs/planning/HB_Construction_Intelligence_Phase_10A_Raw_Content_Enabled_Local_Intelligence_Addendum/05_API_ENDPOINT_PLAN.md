# 05 API Endpoint Plan

## Objective

All local backend endpoints should be raw-content capable. Starting implementation: email and calendar.

## API behavior

Every relevant endpoint should support:

```text
?include_raw=true|false
?raw_mode=include|redacted|metadata
```

Given the user's stated decision, local UI endpoints may default to raw inclusion when config says:

```yaml
raw_content.default_endpoint_behavior: include_raw
```

## Starting endpoints

Add or extend:

- `GET /api/email/messages`
- `GET /api/email/messages/{message_id}`
- `GET /api/email/threads`
- `GET /api/email/threads/{thread_ref}`
- `GET /api/calendar/events`
- `GET /api/calendar/events/{event_id}`
- `POST /api/action-intelligence/model-context/email`
- `POST /api/action-intelligence/model-context/calendar`
- `POST /api/action-intelligence/extract/email`
- `POST /api/action-intelligence/extract/calendar`

## Response contracts

When raw content is included, response objects should contain:

```json
{
  "raw_content_included": true,
  "raw_content_mode": "include",
  "subject": "...",
  "body_text": "...",
  "body_html": "...",
  "source_refs": ["..."]
}
```

## Endpoint acceptance

- Dev UI can inspect raw email/calendar content.
- Local model context endpoints use actual text.
- Redacted/metadata mode remains available for evidence and diagnostics.
