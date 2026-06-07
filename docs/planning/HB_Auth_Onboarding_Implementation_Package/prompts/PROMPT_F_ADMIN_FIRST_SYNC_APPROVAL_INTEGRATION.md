# Prompt F — Admin First-Sync Approval Integration

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Normalize first-sync approval across source connections and enforce sync eligibility so no live sync can occur before admin approval.

## Scope

- Review existing admin approval / source approval routes, models, and tests.
- Ensure every saved source connection has an approval status.
- Add or adapt admin approval endpoints under `/api/settings/connections/admin/*`.
- Add sync eligibility checks used by any manual or scheduled sync path.
- Ensure Procore project connections participate in the same approval model as Microsoft file/source connections.
- Add admin Settings panel for pending first-sync approvals.

## Non-Scope

- Do not implement actual scheduled sync improvements beyond eligibility checks.
- Do not add source-system writeback.
- Do not expose approval controls to non-admin users.

## Likely Files Touched

- `src/hb_assistant/construction/analytics/routes/*`
- `src/hb_assistant/construction/analytics/view_models/*`
- `src/hb_assistant/construction/analytics/*approval*` if present
- `frontend/src/components/settings/AdminFirstSyncApprovalPanel.tsx`
- `frontend/src/lib/api.ts`
- `tests/test_fastapi_analytics_connection_setup.py`
- `tests/test_fastapi_analytics_auth_onboarding.py`

## Acceptance Criteria

- Saved source connection defaults to pending approval unless repo policy says not required.
- Non-admin cannot approve first sync.
- Sync eligibility returns false until approved.
- Manual sync routes and scheduled sync routes check eligibility.
- Admin can approve/reject pending first-sync requests.
- Approval/rejection emits safe local audit metadata.
- No approval response contains raw source data or auth material.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_auth_onboarding.py -k 'approval or sync'
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_auth_onboarding.py
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Risk Notes

- Scheduled sync may be cross-platform in production; eligibility checks must be backend/domain-level, not only frontend-level.
- Do not rely on disabled UI as the only guardrail.
