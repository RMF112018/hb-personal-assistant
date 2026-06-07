# Security and Guardrail Requirements

## Absolute Prohibitions

Do not serialize any of the following to the frontend, logs, test snapshots, evidence files, or docs generated from runtime values:

- access tokens.
- refresh tokens.
- ID tokens.
- client secrets.
- signed URLs.
- download URLs.
- PEM/private key material.
- raw email bodies.
- raw document text.
- raw prompts/responses.
- local token cache contents.
- local token cache paths.
- raw OAuth callback query dumps.

## No Writeback

No implementation may write to Microsoft Graph, Procore, SharePoint, OneDrive, Outlook, Calendar, or any other source system.

If current configured scopes include broad ReadWrite permissions, the implementation must still enforce no-writeback at application policy level and should narrow permissions where repo truth allows without breaking current tenant setup.

## Setup Is Not Sync

The following actions must not start data collection:

- Connect Microsoft 365.
- Connect Procore.
- Preview Procore project URL.
- Preview SharePoint/OneDrive location.
- Save source connection.
- Configure Outlook/Calendar matching.
- Request first-sync approval.

## Admin First-Sync Rule

First live sync must require admin approval for each source connection.

Minimum approval metadata:

- source type.
- local project.
- safe display label.
- requested by.
- requested at.
- approval status.
- approved/rejected by.
- approved/rejected at.
- reason/note.

## Frontend Response Hygiene

Frontend-safe responses may include:

- source status.
- safe display name.
- account hint.
- tenant hint.
- company hint.
- granted/effective scope names.
- last verified time.
- last sync time.
- pending approval status.
- plain-language message.

Frontend-safe responses must not include:

- tokens.
- secrets.
- local filesystem paths.
- raw external API payloads.
- raw exception tracebacks.

## Test Requirements

Add tests that intentionally search serialized API responses and frontend snapshots for forbidden strings and shapes.

Suggested forbidden-pattern checks:

```text
access_token
refresh_token
id_token
client_secret
Authorization
Bearer 
-----BEGIN
signed_url
download_url
msal-token-cache
procore-token-cache
```

## Logging

Auth logs must use redacted structured events only. Never log callback code, state token, device code, user code, token response, refresh response, or local cache path.
