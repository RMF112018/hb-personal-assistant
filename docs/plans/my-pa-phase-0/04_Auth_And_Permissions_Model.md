# Auth and Permissions Model

Prepared: 2026-05-25

## Known App Registration Facts

| Fact | Value |
| --- | --- |
| App name | HB SharePoint Creator |
| App/client ID | 08c399eb-a394-4087-b859-659d493f8dc7 |
| Object ID | 0d581040-e410-48c0-9360-356686cd9f97 |
| allowPublicClient | True |
| Publisher domain | hedrickbrothers.com |
| Identifier URI | api://08c399eb-a394-4087-b859-659d493f8dc7 |
| Installed client redirect URI | http://localhost |
| Tenant ID | 0e834bd7-628b-42c8-b9ec-ecebc9719be4 |
| SharePoint root | https://hedrickbrotherscom.sharepoint.com/ |
| Certificate key ID | 72b2e600-eac6-4b1b-a4b1-4d48048e6667 |

## Runtime Rule

Use delegated Bobby-user auth for `/me`, mail metadata, message body, calendarView, attachment metadata, file metadata, and controlled eligible file download.

## Token Classification

| Token | Claim Shape | Behavior |
| --- | --- | --- |
| Delegated | `scp` present | Runtime allowed when tenant/user/scope checks pass. |
| App-only | `roles` present and `scp` absent | Not allowed for MVP mail/calendar runtime. |
| Ambiguous | both `scp` and `roles` | Fail closed. |
| Invalid | neither | Fail closed. |

## Cache

```text
~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache.bin
~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache-app.bin
```

- Directories `700`; cache files `600`.
- Keychain wrapping deferred until launchd/headless reliability is validated.
- Cache clear/status/logout CLI required.

## Fail-Closed Conditions

- No delegated token.
- Token does not contain `scp`.
- Token does not identify Bobby.
- Tenant mismatch.
- Mail/calendar command receives app-only token.
- Cache permissions weaker than required.
- App registration changes needed without approval.
