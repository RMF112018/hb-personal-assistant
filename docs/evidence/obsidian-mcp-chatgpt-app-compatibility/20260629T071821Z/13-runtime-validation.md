# Runtime Validation

Local isolated runtime used:

- `HB_PA_CONFIG=/private/tmp/hb-obsidian-chatgpt-runtime/hb-pa-config.yml`
- `public_base_url=https://mcp.bobby-fetting.me`
- local port `127.0.0.1:8017`

Local curl-style probes passed:

- `GET /mcp`: 401 with `WWW-Authenticate`
- `GET /.well-known/oauth-protected-resource`: 200 with resource `https://mcp.bobby-fetting.me/mcp`
- `GET /.well-known/oauth-authorization-server`: 200 with `registration_endpoint`
- `POST /oauth/register`: 201
- `POST /oauth/authorize`: 302 redirect with authorization code redacted from evidence
- `POST /oauth/token`: 200 with access token redacted from evidence

Public probes:

- `https://mcp.bobby-fetting.me/mcp`: 401, but missing the new `WWW-Authenticate` header
- `https://mcp.bobby-fetting.me/.well-known/oauth-protected-resource`: 200 and resource-correct
- `https://mcp.bobby-fetting.me/.well-known/oauth-authorization-server`: 200, but missing `registration_endpoint`

