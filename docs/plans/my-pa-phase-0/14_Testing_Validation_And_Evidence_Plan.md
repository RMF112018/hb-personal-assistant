# Testing, Validation, and Evidence Plan

| Target | Validation |
| --- | --- |
| App manifest facts | Assert appId, public client, redirect URI, key credential. |
| Tenant facts | Confirm tenant ID/domain. |
| Delegated token | Prove `scp` and Bobby user context. |
| /me | Safe select succeeds. |
| Mail metadata/body | List metadata and retrieve one redacted body. |
| Body mention | Body-only Bobby mention included. |
| calendarView | Window retrieves event metadata. |
| Attachments/files | Metadata and controlled download proof. |
| SQLite | Migrations idempotent; source upsert idempotent. |
| Extraction | Schemas accept valid and reject invalid output. |
| Obsidian | Marker preservation and completed-task preservation. |
| Dry-run | No writes while producing plan/output preview. |
| Mutation lockout | Static tests prove no M365 write APIs. |
| Large files | Caps/approval statuses tested. |
| launchd | Plist generation and kickstart verified. |
| Sensitive scan | No secrets/auth/state artifacts in repo. |
