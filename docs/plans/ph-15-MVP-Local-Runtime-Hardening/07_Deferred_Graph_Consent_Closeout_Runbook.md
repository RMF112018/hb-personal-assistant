# 07 — Deferred Graph Consent Closeout Runbook

## Status

Prompt 9 remains deferred until Microsoft Graph delegated permissions / tenant-admin consent are granted.

## Do Not

- Do not replace delegated runtime mail/calendar with app-only access.
- Do not broaden permissions without explicit approval.
- Do not mutate Microsoft 365 data.
- Do not claim Graph proof complete without live delegated proof evidence.

## Post-Consent Command Chain

After IT/admin consent lands:

```bash
git status --short
git rev-parse HEAD

.venv/bin/hb-assistant auth clear-cache --json
.venv/bin/hb-assistant auth login --json
.venv/bin/hb-assistant auth status --json
.venv/bin/hb-assistant diagnostics graph --safe --json
.venv/bin/hb-assistant diagnostics proof delegated-graph --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Expected Proof

- Delegated token exists.
- Token is Bobby-user delegated token, not app-only.
- Scope sanitizer excludes MSAL reserved scopes.
- `/me` succeeds.
- Mail metadata proof succeeds.
- Calendar proof succeeds.
- Drive/file metadata proof succeeds.
- Bounded body inspection proof succeeds.
- Controlled file-download proof succeeds only within approved eligibility gates.
- Sensitive scan remains clean.

## Failure Taxonomy

| Failure | Classification |
|---|---|
| Admin approval still pending | `EXTERNAL_ADMIN_CONSENT_BLOCKER` |
| No token in cache | `DELEGATED_TOKEN_UNAVAILABLE` |
| DNS/network issue | `EXTERNAL_NETWORK_DNS_BLOCKER` |
| 403 after login | `GRAPH_PERMISSION_SCOPE_GAP` |
| App-only token used for mail/calendar | `P0_SECURITY_DESIGN_VIOLATION` |
| Reserved scopes error | `SCOPE_SANITIZER_REGRESSION` |
