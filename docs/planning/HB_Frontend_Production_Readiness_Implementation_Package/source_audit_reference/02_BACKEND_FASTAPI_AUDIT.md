# 02 Backend FastAPI Audit

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


## Overall Backend Assessment

The backend is generally aligned with the governance and local-first constraints. The FastAPI app is optional, route registration is explicit inside `create_app`, role resolution is dependency-based, and core dashboard routes delegate to framework-free services rather than CLI shelling.

## Confirmed Strengths

- `ALLOWED_UI_ROLES` is limited to viewer/operator/admin.
- Invalid `X-HB-UI-Role` values raise `403 invalid_ui_role`.
- Backend default role is viewer; frontend default is operator for local dev.
- `/health` and `/chat/status` exist; chat status is disabled.
- No active `/chat` route is registered.
- Admin/Data Confidence routes call `require_admin_role`.
- Connection preview/save uses local setup state; preview does not persist and save does not start first sync.
- Procore homepage URLs and SharePoint/OneDrive/Microsoft 365 preview policies are implemented in the connection setup service.
- Daily Brief service is presenter/detector only and uses local Markdown files generated externally.
- Today, Projects, My Items, Admin, and Settings routes return advisory metadata envelopes with guardrails.

## Backend Risks / Gaps

- Backend has only aggregate `/api/my-items`; frontend expects section subroutes.
- Project tab read models return object envelopes; frontend subpages expect arrays or `items` arrays.
- `/api/today/important` is exported in frontend API client but not registered in backend.
- Auth setup routes can initiate actual auth/OAuth flows; this is acceptable for Settings onboarding but must remain distinct from read-model/dashboard routes.
- Preferences/admin settings PATCH endpoints are echo/stub-level and should not be described as fully persistent production settings.

## Guardrails

The audited route/service design continues to assert read-only, local-first, no CLI shellout, no external writeback, no raw sensitive response fields, no determinations, and advisory-only posture for dashboard/read-model routes.
