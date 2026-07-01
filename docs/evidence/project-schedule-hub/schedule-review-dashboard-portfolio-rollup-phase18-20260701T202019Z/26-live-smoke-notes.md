# Phase 18 live DB GET-only smoke notes

- Captured at: 2026-07-01T20:55:29.182749+00:00
- Resolved DB: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- HB_ASSISTANT_DB_PATH env: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Mutation policy: GET-only; no POST/PATCH/import/recompute/sync

## HTTP requests

[
  {
    "artifact": "18-live-dashboard-api.json",
    "path": "/api/projects/schedule-review-dashboard",
    "params": null,
    "status_code": 200,
    "elapsed_ms": 2039
  },
  {
    "artifact": "19-live-dashboard-filter-missing.json",
    "path": "/api/projects/schedule-review-dashboard",
    "params": {
      "status": "missing"
    },
    "status_code": 200,
    "elapsed_ms": 1943
  },
  {
    "artifact": "20-live-dashboard-filter-stale.json",
    "path": "/api/projects/schedule-review-dashboard",
    "params": {
      "status": "stale"
    },
    "status_code": 200,
    "elapsed_ms": 1935
  },
  {
    "artifact": "21-live-dashboard-filter-needs-review.json",
    "path": "/api/projects/schedule-review-dashboard",
    "params": {
      "status": "needs_review"
    },
    "status_code": 200,
    "elapsed_ms": 1972
  },
  {
    "artifact": "22-live-dashboard-filter-operator-action.json",
    "path": "/api/projects/schedule-review-dashboard",
    "params": {
      "status": "operator_action_required"
    },
    "status_code": 200,
    "elapsed_ms": 1954
  },
  {
    "artifact": "23-live-portfolio-export.md",
    "path": "/api/projects/schedule-review-dashboard/export",
    "params": {
      "format": "markdown"
    },
    "status_code": 200,
    "elapsed_ms": 2180
  }
]

## Portfolio summary (overview)

{
  "project_count": 6,
  "projects_with_schedule": 1,
  "projects_without_schedule": 5,
  "ready_count": 0,
  "degraded_count": 0,
  "blocked_count": 0,
  "needs_review_count": 1,
  "stale_schedule_count": 0,
  "operator_action_required_count": 5
}

## DB snapshot before

{
  "label": "before",
  "captured_at_utc": "2026-07-01T20:55:09.732952+00:00",
  "db_path": "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
  "files": [
    {
      "path": "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
      "exists": true,
      "size_bytes": 4119887872,
      "mtime_ns": 1782938580581004074,
      "mtime_utc": "2026-07-01T20:43:00.581004+00:00"
    }
  ],
  "pragmas": {
    "journal_mode": "wal",
    "query_only": 0
  },
  "table_row_counts": {
    "schedule_file_imports": 25,
    "procore_ep_projects": 6,
    "project_schedule_review_items": 153,
    "project_schedule_review_item_events": 417,
    "schedule_quality_evaluation_runs": 42,
    "project_schedule_series_membership": 0,
    "project_schedule_named_baseline_review_items": 268
  }
}

## DB snapshot after

{
  "label": "after",
  "captured_at_utc": "2026-07-01T20:55:22.783694+00:00",
  "db_path": "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
  "files": [
    {
      "path": "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
      "exists": true,
      "size_bytes": 4119887872,
      "mtime_ns": 1782938580581004074,
      "mtime_utc": "2026-07-01T20:43:00.581004+00:00"
    }
  ],
  "pragmas": {
    "journal_mode": "wal",
    "query_only": 0
  },
  "table_row_counts": {
    "schedule_file_imports": 25,
    "procore_ep_projects": 6,
    "project_schedule_review_items": 153,
    "project_schedule_review_item_events": 417,
    "schedule_quality_evaluation_runs": 42,
    "project_schedule_series_membership": 0,
    "project_schedule_named_baseline_review_items": 268
  }
}

## Mutation violations

[]

## Redaction QA

passed=True

## Live browser

{
  "screenshot": "25-live-browser-dashboard-overview.png",
  "expected_project_count": 6,
  "stdout": "{\n  \"ok\": true,\n  \"expected_project_count\": 6,\n  \"dom_project_count\": 6,\n  \"screenshot\": \"25-live-browser-dashboard-overview.png\",\n  \"dashboard_url\": \"http://127.0.0.1:5174/projects/all/schedule/review\"\n}"
}
