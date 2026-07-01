# Route Strategy

**STAMP:** 20260701T075049Z

## Chosen approach: query-param routing

| Surface | Canonical URL |
|---------|---------------|
| Frontend | `/projects/{projectKey}/schedule/driver-detail?activity_id=FAB%2FDEL-10&comparison_basis=...&as_of=...` |
| Backend API | `GET /api/projects/{project_key}/schedule/drivers/detail?activity_id=FAB%2FDEL-10&...` |

## Backward compatibility

- Backend: keep `GET .../drivers/{activity_id}/detail` for simple IDs.
- Frontend: keep `.../drivers/:activityId` route; page prefers `activity_id` query param.

## Rejected alternative

`{activity_id:path}` — still ambiguous with proxies and React Router; query param is canonical.

## Link policy (Phase 11 amendments)

- Outbound links use `comparison_basis` only (no duplicate conflicting `basis`).
- No frontend silent fallback to `prior_update` on param conflict — show error instead.
