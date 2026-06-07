# Prompt G — Data Quality Readiness/Freshness Surfaces

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Implement safe data-quality/readiness/freshness surfaces, including the required non-admin sidebar footer indicator and admin diagnostic detail view.

## Scope

- Implement `GET /api/settings/data-quality/summary` safe for all roles.
- Implement `GET /api/settings/data-quality/detail` admin-only.
- Add `DataQualityIndicator` in sidebar footer.
- Dot label: `Data Quality`.
- Dot colors:
  - green for good.
  - yellow for degraded/attention.
  - red for poor/no trusted data.
- Reveal latest update date/time and short status message on hover.
- Admin Settings detail shows source-by-source readiness/freshness/approval/failure details.
- Non-admin does not see diagnostics.

## Non-Scope

- Do not implement source sync.
- Do not expose raw confidence internals to non-admin.
- Do not expose raw source payloads even to admin.

## Likely Files Touched

- `src/hb_assistant/construction/analytics/routes/*`
- `src/hb_assistant/construction/analytics/view_models/*`
- `frontend/src/components/layout/DataQualityIndicator.tsx`
- `frontend/src/hooks/useDataQualitySummary.ts`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/lib/api.ts`
- `tests/test_fastapi_analytics_auth_onboarding.py`

## Acceptance Criteria

- Non-admin sidebar footer renders `Data Quality` with status dot.
- Hover reveals latest update date/time and short message.
- Non-admin cannot access detailed diagnostics.
- Admin can access detailed diagnostics in Settings.
- Good/degraded/poor/unknown states are deterministic and tested.
- Summary response never includes tokens, secrets, local paths, raw content, signed URLs, or raw debug payloads.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py -k 'data_quality or readiness or admin'
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Risk Notes

- Keep non-admin indicator intentionally simple.
- Do not turn the sidebar into an operational dashboard.
- Data Quality should degrade conservatively if freshness cannot be proven.
