# Prompt E — Project Connections Auth-Aware Setup Flow

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Implement the Project Connections setup workflow so users can add, preview, and save Procore and Microsoft source connections without starting sync, then queue first-sync admin approval.

## Scope

- Add typed API helpers for project connection preview/save/list.
- Build Project Connections Settings panel.
- Support Procore project homepage URL input.
- Support SharePoint site/folder URL input where backend route truth supports it.
- Support OneDrive scope configuration where backend route truth supports it.
- Support Outlook/Calendar project matching options, false by default.
- Show auth-aware disabled states if Graph or Procore auth is not valid.
- Show preview result before save.
- Save connection and show pending approval.

## Non-Scope

- Do not implement live sync.
- Do not auto-approve first sync.
- Do not expose raw parsed external payloads.

## Likely Files Touched

- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/settings/ProjectConnectionsPanel.tsx`
- `frontend/src/components/settings/ConnectionPreviewCard.tsx`
- `frontend/src/lib/api.ts`
- `src/hb_assistant/construction/analytics/routes/*`
- `tests/test_fastapi_analytics_connection_setup.py`

## Acceptance Criteria

- User can enter Procore project homepage URL.
- User can preview parsed project metadata.
- Preview states explicitly: no sync started.
- User can save connection.
- Save states explicitly: first sync requires admin approval.
- Saved connection appears with approval status pending/approved/rejected.
- Outlook/Calendar project matching is optional and false by default.
- No source sync starts from preview or save.

## Validation Commands

```bash
python -m pytest tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_settings.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_connection_setup.py
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Risk Notes

- URL parsing must not fetch or scrape raw content unless explicitly governed.
- Preview output must be sanitized.
- Keep admin approval visibly separate from save.
