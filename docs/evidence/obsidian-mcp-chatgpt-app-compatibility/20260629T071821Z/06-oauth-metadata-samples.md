# OAuth Metadata Samples

Protected resource metadata:

```json
{"resource":"https://mcp.bobby-fetting.me/mcp","authorization_servers":["https://mcp.bobby-fetting.me"],"scopes_supported":["obsidian.read","obsidian.write"],"bearer_methods_supported":["header"]}
```

Authorization server metadata:

```json
{"issuer":"https://mcp.bobby-fetting.me","authorization_endpoint":"https://mcp.bobby-fetting.me/oauth/authorize","token_endpoint":"https://mcp.bobby-fetting.me/oauth/token","registration_endpoint":"https://mcp.bobby-fetting.me/oauth/register","response_types_supported":["code"],"grant_types_supported":["authorization_code"],"code_challenge_methods_supported":["S256"],"token_endpoint_auth_methods_supported":["none"],"scopes_supported":["obsidian.read","obsidian.write"]}
```

CIMD is absent by design.

