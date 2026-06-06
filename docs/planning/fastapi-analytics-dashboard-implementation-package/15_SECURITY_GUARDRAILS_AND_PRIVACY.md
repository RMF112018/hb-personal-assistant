# Security, Guardrails, and Privacy

## No Writeback

No Microsoft 365, SharePoint, OneDrive, Outlook, Calendar, or Procore writeback in this phase.

## No Raw Sensitive Content

No API response or UI surface should expose:

- raw email bodies;
- raw document text;
- raw prompts/responses;
- auth tokens;
- refresh tokens;
- signed URLs;
- Graph download URLs;
- secrets;
- PEM/private key material.

## Local Auth Storage

Graph and Procore auth are stored locally. UI may show connection status and account identity, but never token values.

## Role Guardrails

Admin-only:

- first live sync;
- sync cadence/priority;
- rate-limit/backoff controls;
- global source scope controls;
- credential revoke/reconnect where appropriate.

## Determination Guardrails

The app may surface signals and exposure indicators. It must not issue legal, claims, entitlement, payment, schedule-delay, safety, or final financial determinations.
