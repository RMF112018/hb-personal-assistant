# 13 — Redaction scan

Scanned evidence package and N7 sources. No raw tailnet/WAN IPs, tokens, or secrets in committable files.

Policy/deny-pattern mentions of `access_token`, `text-vault.key`, etc. in source config are expected.

Passwords and sudo prompts excluded from committed captures.
