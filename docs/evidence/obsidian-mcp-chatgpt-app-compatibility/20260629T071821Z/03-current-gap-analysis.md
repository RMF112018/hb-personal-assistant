# Current Gap Analysis

Closed in code:
- `/mcp` unauthenticated 401 includes `WWW-Authenticate`.
- DCR accepts public ChatGPT clients through `POST /oauth/register`.
- Registered client redirects are exact-match only.
- Newly issued OAuth access tokens are bound to `https://mcp.bobby-fetting.me/mcp`.
- Fixed Grok client is represented by the same `OAuthClient` abstraction.

Remaining deployment gap:
- Public `https://mcp.bobby-fetting.me` was reachable but still served the pre-change runtime during validation.

