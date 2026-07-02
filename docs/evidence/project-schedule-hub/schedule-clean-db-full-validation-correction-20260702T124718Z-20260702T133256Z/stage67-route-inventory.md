# Stage 6/7 route inventory

| Stage | Method | Route | Role |
|-------|--------|-------|------|
| 6 | GET | /api/projects/tropical/schedule/baselines | viewer |
| 6 | PUT | /api/projects/tropical/schedule/baselines | operator |
| 6 | GET | /api/projects/tropical/schedule/controls | viewer |
| 7 | GET | /api/projects/tropical/schedule/review-items | viewer |
| 7 | POST | /api/projects/tropical/schedule/review-items | operator |
| 7 | PATCH | /api/projects/tropical/schedule/review-items/{id} | operator |
| 7 | POST | /api/projects/tropical/schedule/review-items/promote | operator |

Stage 5 canonical routes (no hub alias):
- GET /api/projects/tropical/schedule
- GET /api/schedules/projects/tropical/versions
