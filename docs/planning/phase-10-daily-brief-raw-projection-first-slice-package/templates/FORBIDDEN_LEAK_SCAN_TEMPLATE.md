# Forbidden Leak Scan Template

Scan generated evidence and proof outputs for classes of forbidden strings.

Do not add real private sentinel values. Use only synthetic sentinels when needed.

Forbidden classes:

- raw email/calendar body markers
- `<html`, `<body`, raw HTML dumps
- `https://teams.microsoft.com`
- `joinUrl`, `join_url` values outside schema/column names
- `Authorization:`
- `Bearer `
- `access_token`
- `refresh_token`
- `client_secret`
- `signedUrl`
- `downloadUrl`
- full recipient arrays
- full attendee arrays
- raw model prompt/response bodies

It is acceptable for evidence to include safe column names like `join_url_policy`, `has_join_url`, or table/column names as long as no actual URL value is emitted.
