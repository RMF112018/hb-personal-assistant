# Repo Truth Audit

- Fresh worktree created from `origin/main`.
- Original checkout had unrelated dirty files:
  - `frontend/src/pages/ScheduleIdentityReviewPage.tsx`
  - `src/hb_assistant/construction/analytics/schedule_import_service.py`
  - `frontend/docs/evidence/project-schedule-hub/`
- Worktree before implementation was clean.
- Installed FastMCP SDK supports `ToolAnnotations` and tool `_meta`, but `FastMCP.list_tools()` has no request/context parameter and returns the global tool manager list. Per-client tool-list filtering is therefore not implemented.

