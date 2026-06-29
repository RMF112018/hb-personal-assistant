# OpenAI MCP Requirements Applied

- Authenticated MCP servers need OAuth discovery through protected resource metadata or a `WWW-Authenticate` challenge.
- OAuth metadata must expose authorization and token endpoints.
- Dynamic Client Registration is implemented as the ChatGPT client-registration path.
- The OAuth `resource` value is preserved into authorization codes and access-token audience validation.
- CIMD is not advertised because it is intentionally disabled.

