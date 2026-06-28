# Security Validation

Covered by tests:

- token is persisted but redacted from API/UI responses
- Grok config returns a placeholder token only
- traversal paths are rejected
- symlink escapes outside the vault root are rejected
- file-size cap is enforced
- result character cap is enforced
- Markdown section reads are bounded
- PDF and DOCX reader wrappers are exercised

Phase 1 writes no notes and does not mutate source documents.
