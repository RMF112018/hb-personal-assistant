# Security Validation

Implemented and tested:

- DCR rejects client secrets.
- DCR requires public client auth method `none`.
- DCR requires exact HTTPS redirect URIs and rejects localhost/private IP redirects.
- Registered client authorization rejects unregistered redirect URIs.
- Authorization-code token exchange validates PKCE.
- Token exchange rejects wrong `resource`.
- Access-token validation requires stored resource/audience.
- Raw access tokens, authorization codes, and code verifiers are not persisted.
- Evidence redacts access tokens, authorization codes, and verifiers.
- Static bearer remains separate and unrestricted.
- Write tools still require `obsidian.write` and existing vault write policy.

