# Runtime MCP Smoke

Runtime smoke used a temporary vault and a bearer token. The response and audit payload scan confirmed the token and raw note bodies were not exposed.

```json
{
  "health_ok": true,
  "blocking_issue_codes": [],
  "initialize_status": 200,
  "initialized_status": 202,
  "tools_list_status": 200,
  "tools": [
    "list_directory",
    "search_vault",
    "read_file",
    "create_note",
    "patch_note"
  ],
  "create_status": 200,
  "patch_status": 200,
  "disabled_contains_code": true,
  "protected_contains_code": true,
  "mismatch_contains_code": true,
  "backup_recorded": true,
  "audit_event_count": 5,
  "raw_content_leaked": false,
  "note_replaced_on_disk": true
}
```

