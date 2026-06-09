# 205. Frontend Connections UI Cards and Workflows

Date: 2026-06-07

Package: Graph/Procore Dev UI Connections Implementation Package 1.3.0

## Decision

P06 adds a new "Source Connections" surface in Settings: `SourceConnectionsPanel` (rendered via `SectionCard`) plus `GraphSourceCard` and `ProcoreSourceCard`. The panel and cards are bound to the P05 `/api/sources/*` + scheduler/environment client (getEnvironment, getSourcesStatus, getSchedulerStatus, the refresh* and *SourceAuth* starters). They display:

- Environment/mode banner (source_refresh_mode + live_refresh.{available,enabled,reason})
- Last local update (via scheduler last_successful_schedule_date + timeAgo helper)
- Per-source state (via new getSourceStateCopy), last-update + mode, warnings (scope/missing_config/missing_mapping + pending list), and actions
- Panel-level refresh actions: Dry-run and Local (always enabled, operator-safe); Live (disabled unless enabled; otherwise confirmation-gated via native confirm before refreshSourcesLive(true))
- Receipts shown via safeDisplayText only (status + live_mode); no raw JSON/tokens

The existing onboarding `AccountConnectionsPanel` + `GraphConnectionCard`/`ProcoreConnectionCard` (device-flow "Get Started" + settings variant) are left completely untouched.

All surfaces reuse the committed shell primitives: `SectionCard`, `ErrorState`/`LoadingState`/`EmptyState`/`DisconnectedState`/`TechnicalDetails`, `safeDisplayText` + `getErrorCopy` from errorCopy, `getSourceStateCopy` (added to statusCopy), and a new zero-dep `timeAgo`/`formatLastUpdate`.

## Rationale

Operators need a consolidated, always-safe view of source connectivity, freshness, dev/prod mode, and gated refresh controls in Settings without exposing secrets or triggering live work accidentally. The design keeps the "connect accounts for first use" flow (onboarding cards) separate from the operational "source health + refresh" surface so regressions in Get Started are impossible.

State, warnings, and actions are derived from the P05 normalized contracts so the UI stays presentation-only. Live refresh is fail-closed by default in dev and confirmation-gated in prod to match scheduler/orchestrator policy.

## Guardrails

- No raw tokens, cache paths, flow_ids, PEMs, or full bodies ever rendered or logged by these components.
- Dry-run and local refresh are always safe (no external side effects).
- Live refresh requires explicit confirm and is disabled when the environment/config marks it unavailable.
- Technical details (if any) are collapsed by default via TechnicalDetails.
- All dynamic text goes through safeDisplayText or the typed copy helpers.
- Onboarding cards and their auth flows are not modified.

## State / Last Update / Mode / Warning / Action Model

- States (getSourceStateCopy): connected_valid (success), reauth_required / connected_stale_reauth_required (danger), cache_present_unverified (attention), not_connected/never_connected (attention), not_configured (neutral), configured_not_connected (attention). Fallback neutral "Unknown".
- Last local update: scheduler last_successful_schedule_date formatted by timeAgo ("5m ago", "yesterday", "—").
- Mode: source_refresh_mode (mock_data vs local_or_gated_live) + live_refresh.enabled/reason for banner and Live button state.
- Warnings (inline, not raw):
  - Graph: scope_presence.missing, reauth_required.
  - Procore: missing_config, missing_mapping + list of pending_projects, reauth.
- Actions:
  - Panel: Dry-run → refreshSourcesDryRun, Local → refreshSourcesLocal (always), Live (gated) → confirm? refreshSourcesLive(true). Receipt status/live_mode shown safely.
  - Cards: Connect (if not connected) → start*SourceAuth (device code or OAuth prompt showing only safe fields; polls status; onComplete refetches), Refresh-auth → refresh*SourceAuth. Never tokens. Errors via ErrorState (safe copy); advanced via collapsed TechnicalDetails.

## Gated Live-Refresh Behavior

Live button is disabled when live_refresh.enabled is false (dev/mock or scheduler config). When enabled, click shows a native confirm dialog before calling the live endpoint with confirm body. The returned receipt (status, live_mode, reason on block) is rendered via safeDisplayText only.

## Reuse of Primitives + statusCopy / timeAgo

- UI primitives: SectionCard (panel container), ErrorState/LoadingState (top-level states), TechnicalDetails (collapsed admin details), safeDisplayText + getErrorCopy (all dynamic/advisory text).
- Status: getSourceStateCopy added to statusCopy.ts (additive; reuses StatusCopy type + copyFrom fallback). Existing auth/freshness/data quality copies untouched.
- Time: new pure frontend/src/lib/timeAgo.ts (timeAgo + formatLastUpdate). No date libs.
- Badge tones: copy.tone drives label + optional badge-* classes for visual weight.

## Onboarding Cards Left Intact

AccountConnectionsPanel, GraphConnectionCard, and ProcoreConnectionCard (the device-code/OAuth "connect accounts" surfaces used by Get Started and the Account Connections section) are not imported, modified, or referenced by the new Source Connections panel/cards. Their API surface (/api/settings/connections/*) remains the one used for first-time + reauth device flows.

## Files Changed (P06 only)

New:
- frontend/src/components/settings/SourceConnectionsPanel.tsx
- frontend/src/components/settings/GraphSourceCard.tsx
- frontend/src/components/settings/ProcoreSourceCard.tsx
- frontend/src/lib/timeAgo.ts
- frontend/src/components/settings/SourceConnectionsPanel.test.tsx
- docs/architecture/205-frontend-connections-ui-cards.md

Edit (minimal):
- frontend/src/lib/statusCopy.ts (added getSourceStateCopy + sourceStateCopy map)
- frontend/src/pages/SettingsPage.tsx (import + <SourceConnectionsPanel/> placement next to AccountConnectionsPanel)

Verification (post-changes): cd frontend && npx vitest run src/components/settings (then full), npx eslint on new files, npx tsc -b (0 errors). Live: /settings shows the panel with dev/mock banner, states + warnings, Live disabled, Dry/Local enabled, actions safe, no raw leaks.

## Closeout

All work committed on codex/p06-connections-ui (never main) with subject `feat(frontend): P06 — Connections UI Cards and Workflows (Graph/Procore Dev UI Connections Implementation Package 1.3.0)` and Co-Authored-By trailer. Architecture doc 205 created. Full verification suite run. Only P06 paths staged (force-add for any lib/ timeAgo.ts due to packaging .gitignore rule).
