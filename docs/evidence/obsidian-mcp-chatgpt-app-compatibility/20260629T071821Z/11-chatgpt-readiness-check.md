# ChatGPT Readiness Check

Settings readiness validates:

- `public_base_url`
- `/mcp` `WWW-Authenticate`
- protected resource metadata
- authorization server metadata
- `registration_endpoint`
- CIMD unadvertised
- no stale `trycloudflare.com`
- POST DCR validation
- ChatGPT initial read-only scope

ChatGPT manual setup result: not completed. The public domain was still serving the pre-change runtime during validation, so ChatGPT setup would not yet see DCR or the `/mcp` challenge.

