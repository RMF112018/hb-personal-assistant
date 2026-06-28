# Sample Health Check

Local runtime smoke after installing the optional `mcp` SDK:

```json
{
  "mcp_endpoint": "/mcp",
  "initialize_status": 200,
  "initialized_status": 202,
  "tools_list_status": 200,
  "health_ok": true,
  "blocking_issue_codes": [],
  "mcp_sdk_check": {
    "name": "mcp_sdk",
    "status": "pass",
    "detail": "MCP SDK available"
  },
  "streamable_http_app_check": {
    "name": "streamable_http_app",
    "status": "pass",
    "detail": "Streamable HTTP app can be initialized when SDK is installed"
  },
  "tools": ["list_directory", "search_vault", "read_file"],
  "service_state": "running",
  "token_value_leaked": false
}
```

Health checks passed for vault existence/readability, configured scope safety, PDF extraction dependency, DOCX extraction dependency, MCP SDK availability, Streamable HTTP initialization, caps configuration, tool registry, and HTTP port availability.
