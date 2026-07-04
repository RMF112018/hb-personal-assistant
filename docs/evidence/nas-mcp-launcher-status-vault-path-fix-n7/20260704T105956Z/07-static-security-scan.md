# 07 — Static security scan

Redaction scan command run against evidence (excluding `local-sensitive/`), changed NAS MCP sources, deploy/mcp, and tests.

## Policy

- Approved NAS vault host path in deploy evidence: acceptable
- Deny-pattern mentions (token cache, text-vault.key): acceptable policy text
- Old Mac vault path: must not appear in committable code (verified by test)

## Result

**PASS** — no tailnet/WAN IPs, tokens, secrets, or Mac home paths in committable artifacts.
