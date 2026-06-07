# 04 Route/API Contract Matrix

Generated from the audit package. Reconfirm against current repo truth before implementing.

| Method | Path | Backend implemented | Frontend surface | Alignment |
|---|---|---|---|---|
| GET | `/api/today` | yes | TodayPage | compatible |
| GET | `/api/today/important` | no | api.ts exported only | unused_export_gap |
| GET | `/api/today/changes` | yes | TodayPage | compatible |
| GET | `/api/today/meetings` | yes | TodayPage | compatible |
| GET | `/api/today/action-items` | yes | TodayPage | compatible |
| GET | `/api/today/portfolio-signals` | yes | TodayPage | compatible |
| GET | `/api/today/daily-brief` | yes | TodayPage | compatible |
| GET | `/api/daily-brief/status` | yes | SettingsPage | compatible |
| GET | `/api/daily-brief/latest` | yes | api.ts | compatible |
| POST | `/api/daily-brief/configure` | yes | SettingsPage | compatible |
| POST | `/api/daily-brief/generate-setup-instructions` | yes | SettingsPage | compatible |
| POST | `/api/daily-brief/validate-output-folder` | yes | SettingsPage | compatible |
| POST | `/api/daily-brief/detect-latest` | yes | SettingsPage | compatible |
| GET | `/api/projects/portfolio` | yes | ProjectsPage | shape_mismatch_project_list |
| GET | `/api/projects/all/overview` | yes | ProjectDashboardPage | partial_shape_mismatch |
| GET | `/api/projects/{project_key}/overview` | yes | ProjectDashboardPage | partial_shape_mismatch |
| GET | `/api/projects/{project_key}/meetings` | yes | ProjectMeetingsPage | shape_crash_risk |
| GET | `/api/projects/{project_key}/field-operations` | yes | ProjectFieldOperationsPage | shape_crash_risk |
| GET | `/api/projects/{project_key}/cost-time` | yes | ProjectCostTimePage | shape_crash_risk |
| GET | `/api/my-items` | yes | MyItemsPage | compatible_but_underused |
| GET | `/api/my-items/action-items` | no | MyItemsPage | 404_gap |
| GET | `/api/my-items/meetings` | no | MyItemsPage | 404_gap |
| GET | `/api/my-items/correspondence` | no | MyItemsPage | 404_gap |
| GET | `/api/my-items/files` | no | MyItemsPage | 404_gap |
| GET | `/api/my-items/followed-projects` | no | MyItemsPage | 404_gap |
| GET | `/api/admin` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/admin/source-sync-health` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/admin/workflow-job-health` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/admin/evidence-guardrails` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/admin/retrieval-ai-quality` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/admin/permissions-governance` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/admin/data-completeness` | yes | AdminDataConfidencePage | role_403_ux_gap |
| GET | `/api/settings` | yes | api.ts | compatible |
| GET | `/api/settings/accounts` | yes | SettingsPage | raw_json_ux_gap |
| GET | `/api/settings/projects` | yes | SettingsPage | raw_json_ux_gap |
| GET | `/api/settings/sources` | yes | SettingsPage | raw_json_ux_gap |
| GET | `/api/settings/keywords` | yes | SettingsPage | raw_json_ux_gap |
| GET | `/api/settings/daily-brief` | yes | SettingsPage | raw_json_ux_gap |
| GET | `/api/settings/preferences` | yes | SettingsPage | stub |
| GET | `/api/settings/admin-sync` | yes | SettingsPage | admin_only |
| PATCH | `/api/settings/preferences` | yes | SettingsPage | echo_stub |
| PATCH | `/api/settings/admin` | yes | SettingsPage | echo_stub |

## Immediate Contract Targets

Prompt 16 must resolve every `404_gap`, `shape_crash_risk`, and BrowserRouter navigation mismatch before UX polish begins.

## Preferred Fix Order

1. Stabilize frontend API client/adapters.
2. Add backend compatibility routes only where they match product direction and simplify the UI contract.
3. Update OpenAPI/app-shell route assertions after route changes.
4. Add browser smoke coverage for every expected route/API call.
