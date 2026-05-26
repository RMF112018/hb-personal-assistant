# Security and Redaction Requirements

## Non-Negotiable Rules

- Microsoft 365 writeback remains disabled.
- Do not add Graph POST, PUT, PATCH, or DELETE wrappers.
- Do not persist full email bodies.
- Do not persist full file contents in SQLite.
- Do not log Authorization headers.
- Do not print raw tokens.
- Do not commit token caches, `.pem`, `.pfx`, `.key`, `.crt`, `.cer`, SQLite DB files, or local `.env` files.

## Bounded Body Processing

Allowed:

- Retrieve body for a bounded candidate set.
- Process body in memory.
- Convert HTML to text in memory.
- Detect Bobby aliases.
- Store detection flags and optional redacted match window.

Not allowed:

- Store full body.
- Write full body to evidence.
- Embed full body into vector store.
- Send full body to external services.

## Sensitive Scanner Output

Allowed output:

```json
{
  "category": "oauth_token_field",
  "path": "docs/evidence/example.json",
  "line": 42,
  "severity": "high"
}
```

Forbidden output:

```json
{
  "matched_value": "actual-token-or-secret"
}
```

## Public Repo Caution

The repository appears public. The agent must assume every committed artifact is visible outside the company. Evidence must be sanitized accordingly.
