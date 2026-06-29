# Grok Regression

Covered by `tests/test_obsidian_mcp_oauth.py`:

- Fixed client ID `hb-obsidian-grok` still works.
- Existing Grok authorization-code with PKCE flow still exchanges for a token.
- Legacy Grok redirect compatibility is preserved through the fixed `OAuthClient` abstraction.
- Static bearer remains unrestricted and separate from OAuth scope enforcement.

