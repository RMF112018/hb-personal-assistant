# UI Before / After Notes

## Before

- `/schedules/quality` rendered `Schedule quality`.
- Schedule subnav label was `Quality`.
- Page primarily consumed `/api/schedules/versions/{schedule_version_key}/quality`.
- Version diff remained a separate route.
- Baseline/package/capability evidence was not composed into the page.

## After

- `/schedules/quality` renders `Schedule Health`.
- `/schedules/health` renders the same page.
- Schedule subnav label is `Schedule Health`.
- Page primarily consumes V75 `health-data`.
- PM cards appear above standards detail:
  - Schedule health
  - Update reliability
  - Finish movement vs prior
  - Baseline drift
  - Critical path confidence
  - Top PM action
- Evidence sections include:
  - Available Schedule Evidence
  - What Changed Since the Prior Schedule?
  - Baseline Health
  - Critical Path and Float Evidence
  - DCMA 14-Point Assessment
  - GAO / AACE Categories
  - Findings
  - Unavailable / Deferred Analysis

Old imports without V75 package metadata render a limited-data state. XER-only baseline references render as `Requires companion file`, not as a failed import.
