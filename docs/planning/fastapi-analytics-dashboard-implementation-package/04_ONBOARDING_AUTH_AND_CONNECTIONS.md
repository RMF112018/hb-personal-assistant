# Onboarding, Authentication, and Connections

## First-Run Wizard

1. Welcome and purpose.
2. Authenticate Microsoft Graph through device login.
3. Authenticate Procore through the existing OAuth flow.
4. Add first project.
5. Paste source URLs.
6. Review detected source scopes.
7. Review suggested project keywords.
8. Admin schedules first sync.
9. Confirm dashboard readiness.

## Graph Authentication

Trigger Microsoft Graph device login on first login/setup. Store authentication locally using the existing token-cache posture. Show connected account status, reconnect, revoke local credentials, and auth expiry state. Never show token values.

## Procore Authentication

Trigger Procore OAuth setup on first login/setup. Store auth locally. Show connected/disconnected state, reconnect, revoke local credentials, and access validation. Never show token values.

## Connection Philosophy

Users should paste URLs, not configure APIs.

- Paste Procore project homepage URL.
- Paste SharePoint site or folder link.
- Select OneDrive folder scope.
- Confirm detected project/source.
- Let admin schedule first sync if required.

## Validation Before Sync

Validate URL shape, extract IDs, resolve accessible source, preview detected scope, show potential large-scope warning, and require Admin first-sync approval.
