# Phase 15 Repo-Truth Audit

**Base:** `258e043b` (Phase 14 merged)  
**Date:** 2026-07-01

## Identity trust computation

| Location | Role |
|----------|------|
| `schedule_identity_repository.py` | Persists `schedule_identities`, `schedule_version_identity_matches`, `schedule_identity_manual_actions` |
| `schedule_trust_service.py` | Pre-commit preview warnings, post-commit membership guardrails, hub `build_trust_envelope`, operator `set_series_membership` |
| `project_schedule_summary_service.py` | Resolves current version, `schedule_trust`, `identity_review`, readiness gates |
| `project_schedule_analytics_trust_service.py` (Phase 14) | `analytics_trust_status` ledger; Phase 15 extends with `identity_gate` |

## Persistence

- **V77/V78 tables:** `schedule_identities`, `schedule_version_identity_matches`, `schedule_identity_manual_actions`
- **Hub membership:** `project_schedule_series_membership` via `ProjectScheduleHubRepository.upsert_membership`
- **Operator writes:** Existing API routes for reassign/split/merge/series-membership (operator-gated)

## Import gating (pre-Phase 15)

- Preview: `trust_preview` warnings (overlap, mismatch, supersede) — no structured identity trust block
- Commit: identity resolution persisted; `evaluate_import_guardrail` sets membership pending
- **Gap:** `trust_preview` leaked `accepted_schedule_version_key` / `preview_schedule_version_key` in PM payload

## Hub / controls / export gating (pre-Phase 15)

- Hub: inline `TrustBanner` on `schedule_trust.status !== trusted`
- Controls: no identity section; analytics trust from Phase 14 without identity gate
- Export: Phase 14 analytics trust section without identity fields
- **Gap:** CPM complete + identity pending could yield `analytics_trust_status=ready` in edge cases

## Operator review workflow

- **Exists:** `/schedules/identity-review` (`ScheduleIdentityReviewPage`) with assign/split/merge (operator role)
- **API:** `GET /api/schedules/projects/{project_key}/identity-review`, series-membership POST
- Phase 15: enrich PM-safe messaging; link from hub/controls/import via `identity_review_url`

## Raw ID leaks (pre-Phase 15)

- `trust_preview` version keys in import preview
- `technical_evidence.schedule_identity_key` in hub (collapsed — acceptable)
- `identity_match` on commit via `public_match()` includes raw keys
- `ScheduleIdentityReviewPage` shows truncated version keys (operator surface — acceptable)

## Phase 15 implementation

- New: `project_schedule_identity_trust_service.py` — PM-safe `identity_trust` read model
- Extended: analytics ledger with `identity_gate` as first-class gate (blocked overrides CPM-ready)
- Wired: import preview/status, hub, controls, export memo
- Frontend: extracted `TrustBanner.tsx` with identity + analytics trust states
- Redacted: `_pm_trust_preview()` strips version keys from import preview

## Phase 15B (deferred)

- No new persistence layer invented; existing manual actions + membership APIs used for operator writes
- Document any net-new override audit fields if product requires reason capture beyond existing `review_reason`
