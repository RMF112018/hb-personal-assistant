# Sensitive Data Guardrails

Do not commit, print, log, or include in evidence:

- Microsoft access tokens or refresh tokens
- MSAL cache content
- private keys, PEMs, certificates, or passwords
- full email bodies
- full file contents
- unredacted message subjects if they may contain sensitive data
- unredacted sender/recipient lists where not needed
- local secret paths beyond safe high-level diagnostics

Allowed in evidence:

- counts
- booleans
- source_record_id values
- redacted excerpts
- bounded parser excerpt previews
- sanitized error classifications
- command exit codes
- safe path readiness booleans
