# WWW-Authenticate Proof

Local isolated runtime:

```http
HTTP/1.1 401 Unauthorized
content-type: application/json
www-authenticate: Bearer resource_metadata="https://mcp.bobby-fetting.me/.well-known/oauth-protected-resource", scope="obsidian.read"

{"detail":"unauthorized"}
```

Public deployment drift observed:

```http
HTTP/2 401
content-type: application/json

{"detail":"unauthorized"}
```

The public runtime must be updated/restarted from this branch before ChatGPT setup can use the new challenge.

