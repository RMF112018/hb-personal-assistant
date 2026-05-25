# Manual Approval Gates

| Gate | Trigger |
| --- | --- |
| App registration changes | Any scope, redirect, credential, or consent change. |
| M365 write-back | Any mail/calendar/task/file mutation. |
| Large files | Download/parse above 300 MB. |
| External LLM | Any cloud model or embedding service. |
| OCR | Any scanned PDF/image OCR. |
| Native CAD/Revit | Any DWG/RVT/RFA parser or converter. |
| Keychain wrapping | Changing MVP cache protection. |
| Other mailbox | Shared mailbox or non-Bobby mailbox access. |
| Tenant-wide crawl | Broad SharePoint/OneDrive discovery. |
| Persist full bodies/text | Storing full email bodies or parsed files. |
| Destructive local state | Deleting SQLite/evidence without backup. |
| Weekend unattended automation | Changing manual-only weekend behavior. |
