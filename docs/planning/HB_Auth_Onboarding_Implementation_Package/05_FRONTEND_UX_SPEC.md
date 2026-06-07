# Frontend UX Specification

## Required Routes

- `/get-started`
- `/settings`
- Existing main app routes remain intact.

## App Startup Routing

On app mount:

1. Call `GET /api/onboarding/readiness`.
2. If `get_started_required === true`, route to `/get-started`.
3. If `main_app_allowed === true`, route normally to the app shell.
4. If `reauth_required` contains sources, render source-specific reauth prompts.
5. Do not treat stale auth as first-time onboarding until automated refresh has failed and no usable prior setup exists.

## Get Started Screen

Purpose: dedicated landing screen for fully unauthenticated sessions.

Content requirements:

- Plain-language setup summary.
- Explain that connecting an account does not start sync.
- Explain that preview/save do not start sync.
- Explain that first live sync requires admin approval.
- Primary action: `Connect Microsoft 365`.
- Secondary action: `Connect Procore`.
- Stepper or cards:
  1. Connect accounts.
  2. Add project/source connections.
  3. Preview setup.
  4. Save setup.
  5. Admin approval.
  6. Governed sync.

## Account Connections Settings

Replace debug-style load buttons with real cards.

### Microsoft 365 Card

States:

- Not connected.
- Connecting.
- Waiting for Microsoft sign-in.
- Connected.
- Needs re-auth.
- Refreshing.
- Error.

Actions:

- Connect Microsoft 365.
- Copy/open verification URL.
- Poll/complete sign-in.
- Try refresh.
- Disconnect local account.

Never display token/cache path/raw JSON.

### Procore Card

States:

- Not connected.
- Opening Procore authorization.
- Waiting for callback.
- Connected.
- Needs re-auth.
- Refreshing.
- Error.

Actions:

- Connect Procore.
- Open authorization URL.
- Use manual code fallback.
- Try refresh.
- Disconnect local account.

Never display token/cache path/raw JSON.

## Project Connections Settings

Required controls:

- Select local project.
- Add Procore project homepage URL.
- Add SharePoint site/folder URL.
- Configure OneDrive scope.
- Configure Outlook/Calendar matching only, optional and false by default.
- Preview parsed setup.
- Save connection.
- Show pending admin approval.

Required copy:

- `Previewing does not start sync.`
- `Saving does not start sync.`
- `First live sync requires admin approval.`

## Sidebar Data Quality Indicator

Non-admin users must see only a simple footer indicator.

Display:

```text
● Data Quality
```

Dot mapping:

- Green: `good`.
- Yellow: `degraded` or `unknown` with prior setup.
- Red: `poor`, disconnected, failed sync, or no trusted data.

Hover tooltip examples:

Good:

```text
Data Quality: Good
Last updated: Jun 7, 2026 at 8:00 PM
Sources are current.
```

Degraded:

```text
Data Quality: Needs attention
Last updated: Jun 6, 2026 at 8:00 PM
Some approved sources are stale or pending sync.
```

Poor:

```text
Data Quality: Poor
Last updated: Not available
No approved source data has been collected yet.
```

Admin users may click through to detailed diagnostics in Settings.

## Components To Add Or Refactor

Likely components:

- `frontend/src/pages/GetStartedPage.tsx`
- `frontend/src/components/settings/AccountConnectionsPanel.tsx`
- `frontend/src/components/settings/GraphConnectionCard.tsx`
- `frontend/src/components/settings/ProcoreConnectionCard.tsx`
- `frontend/src/components/settings/ProjectConnectionsPanel.tsx`
- `frontend/src/components/settings/ConnectionPreviewCard.tsx`
- `frontend/src/components/settings/AdminFirstSyncApprovalPanel.tsx`
- `frontend/src/components/layout/DataQualityIndicator.tsx`
- `frontend/src/hooks/useOnboardingReadiness.ts`
- `frontend/src/hooks/useDataQualitySummary.ts`
- `frontend/src/lib/api.ts`

Use existing design system conventions in the repo. Do not introduce a new UI framework.
