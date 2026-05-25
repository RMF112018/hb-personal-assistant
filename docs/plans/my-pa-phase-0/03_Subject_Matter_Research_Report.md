# Subject Matter Research Report

Prepared: 2026-05-25

## Research Findings

### Identity and MSAL

- Delegated permissions represent signed-in user access; application permissions represent app-only access. Runtime mailbox/calendar/file workflows must therefore use delegated Bobby-user auth.
- Certificate credentials prove confidential-client/app-only capability only. They do not prove delegated mailbox/calendar readiness.
- Public client desktop auth is suitable for the Bobby-only local CLI, while app-only cache/proof must remain segregated.
- Token classification must enforce `scp` for delegated runtime and reject `roles`-only tokens for mail/calendar.

### Graph Mail

- Use bounded message listing with `$select`, paging, immutable IDs where supported, and body retrieval only when needed.
- Body retrieval is required for Bobby body-mention detection but must never be logged in full.
- Attachments are metadata-first; content retrieval requires file eligibility gates.

### Graph Calendar

- `calendarView` is the MVP endpoint for morning windows because it expands occurrences/exceptions in a date range.
- `/events` is secondary for direct/non-expanded event listing.
- Delta query is a later optimization after deterministic polling works.

### Graph Files

- OneDrive and SharePoint files are represented as `driveItem`.
- File metadata is required before content download.
- `Files.ReadWrite.All` may be present, but MVP runtime remains read-only.
- Respect Graph throttling and `Retry-After`.

### Local Parsing

- PyMuPDF primary for selectable-text PDF extraction; pypdf fallback for metadata/encryption.
- python-docx, openpyxl/pandas, python-pptx, csv, mimetypes, and hashlib cover MVP document types.
- OCR, encrypted files, and native CAD/Revit parsing are out of MVP.

### Obsidian

- Vault conventions support Daily Notes, AI Outputs, templates, YAML frontmatter, wikilinks, Dataview, Templater, and Tasks.
- The package defines HB Daily Brief markers because no established HB-specific marker pair existed.
- Plain Markdown tasks remain primary; Tasks metadata only when high-confidence.

### Ollama / SQLite / launchd

- Ollama structured outputs support schema-constrained local extraction.
- SQLite WAL and migrations support local durable state.
- sqlite-vec is acceptable only after deterministic retrieval works.
- launchd should trigger the user agent; catch-up-after-wake is implemented in app logic with a run ledger.

## Source Register

See `research/Research_Source_Register.md`.

# Research Source Register

| Area | Source | URL |
| --- | --- | --- |
| Microsoft Identity | MSAL Python | https://learn.microsoft.com/en-us/entra/msal/python/ |
| Microsoft Identity | Permissions and consent | https://learn.microsoft.com/en-us/entra/identity-platform/permissions-consent-overview |
| Microsoft Identity | Scopes and permissions | https://learn.microsoft.com/en-us/entra/identity-platform/scopes-oidc |
| Microsoft Identity | Application vs delegated token claims | https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/application-delegated-permission-access-tokens-identity-platform |
| Microsoft Identity | Certificate credentials | https://learn.microsoft.com/en-us/entra/identity-platform/certificate-credentials |
| Microsoft Identity | Redirect URI best practices | https://learn.microsoft.com/en-us/entra/identity-platform/reply-url |
| Exchange | RBAC for Applications | https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac |
| Graph Mail | Outlook mail API overview | https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview?view=graph-rest-1.0 |
| Graph Mail | List messages | https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0 |
| Graph Mail | Get message | https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0 |
| Graph Mail | Message resource | https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0 |
| Graph | Get attachment | https://learn.microsoft.com/en-us/graph/api/attachment-get?view=graph-rest-1.0 |
| Graph Calendar | Calendar resource | https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0 |
| Graph Calendar | List calendarView | https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0 |
| Graph Calendar | List events | https://learn.microsoft.com/en-us/graph/api/calendar-list-events?view=graph-rest-1.0 |
| Graph Calendar | Delta query events | https://learn.microsoft.com/en-us/graph/delta-query-events |
| Graph Files | Working with files | https://learn.microsoft.com/en-us/graph/api/resources/onedrive?view=graph-rest-1.0 |
| Graph Files | driveItem resource | https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0 |
| Graph Files | Get driveItem | https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0 |
| Graph Files | Download driveItem content | https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0 |
| Graph | Microsoft Search API | https://learn.microsoft.com/en-us/graph/search-concept-overview |
| Graph | Query parameters | https://learn.microsoft.com/en-us/graph/query-parameters |
| Graph | Paging | https://learn.microsoft.com/en-us/graph/paging |
| Graph | Throttling | https://learn.microsoft.com/en-us/graph/throttling |
| Parsing | PyMuPDF | https://pymupdf.readthedocs.io/ |
| Parsing | pypdf | https://pypdf.readthedocs.io/ |
| Parsing | python-docx | https://python-docx.readthedocs.io/ |
| Parsing | openpyxl | https://openpyxl.readthedocs.io/ |
| Parsing | python-pptx | https://python-pptx.readthedocs.io/ |
| Python | csv | https://docs.python.org/3/library/csv.html |
| Python | mimetypes | https://docs.python.org/3/library/mimetypes.html |
| Python | hashlib | https://docs.python.org/3/library/hashlib.html |
| SQLite | WAL | https://sqlite.org/wal.html |
| SQLite | PRAGMA | https://sqlite.org/pragma.html |
| Vector | sqlite-vec | https://github.com/asg017/sqlite-vec |
| Ollama | Structured outputs | https://docs.ollama.com/capabilities/structured-outputs |
| macOS | Apple launchd jobs | https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html |
| macOS | launchd.plist man page | https://www.manpagez.com/man/5/launchd.plist/ |
