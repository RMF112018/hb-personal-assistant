# Addendum Security Guardrails

## Path Repair

- Do not run `sudo` automatically from the app.
- Do not widen auth directory permissions beyond `0700`.
- Token cache files must remain `0600`.
- Non-sensitive DB/cache directories may be `0755` if needed for normal local operation.

## Body Mention Detection

Allowed:

- Bounded body fetch.
- In-memory HTML-to-text.
- Alias detection.
- Redacted match window.

Forbidden:

- Persisting raw body.
- Logging raw body.
- Embedding full body.
- Writing full body to Obsidian/evidence.

## Delegated Graph Proof

- Use delegated token only for user-context mail/calendar/file reads.
- App-only proof should prove rejection or unavailability for runtime mail/calendar.
- No Graph mutation methods may be introduced.

## Evidence

- Output paths and status are allowed.
- Token values are forbidden.
- PEM contents are forbidden.
- Full email/file content is forbidden.
