# Graph Integration Specification

Prepared: 2026-05-25

## Standards

- Centralize all HTTP calls in `GraphHttpClient`.
- Use delegated token for runtime.
- Add `Prefer: IdType="ImmutableId"` where supported.
- Use `$select`, `$top`, paging through `@odata.nextLink`, and Retry-After handling.
- Do not synthesize skip tokens.
- Do not log authorization headers or full content.

## Mail

Inbound lookback: 5 days. Sent lookback: 7 days.

Store minimal fields: ID, immutable ID, conversation ID, internetMessageId, redacted subject/hash, sender domain/hash, recipients hashes, received/sent date, bodyPreview redacted, hasAttachments, webLink.

Body retrieval is staged and bounded. Body text is used for mention/action extraction and not logged in full.

## Calendar

Use `/me/calendarView` for yesterday/today/next 2 business days. Store iCalUId, ID, subject hash/redaction, organizer hash, attendees hashes, start/end, timezone, location redaction, online meeting flag/link, webLink, hasAttachments, cancellation/private indicators.

## Attachments

List metadata first. Download only if parent source is relevant and file eligibility gates pass. Support fileAttachment, itemAttachment, and referenceAttachment metadata.

## Files

Resolve driveItem metadata before content download. Download only driveItems with a `file` facet and only within size/type/manual-approval controls.

## Throttling

```yaml
max_retries: 5
respect_retry_after: true
base_backoff_seconds: 2
max_backoff_seconds: 60
retry_statuses: [429, 500, 502, 503, 504]
non_retry_statuses: [400, 401, 403, 404]
```

## Forbidden Calls

No sendMail, draft creation, mark read/unread, categories/flags, calendar creation/update/delete, To Do tasks, OneDrive/SharePoint upload/update/delete.
