# Prompt 09 TODAY PROJECTS MY ITEMS

Implement the primary user-facing screens that make the app feel like a low-friction time-management and construction-intelligence platform.

## Today page

Implement `/today` as the primary landing page.

Sections:

- Important Today
- Daily Brief
- Today's Meetings
- What Changed
- Action Items
- Portfolio Signals

The Daily Brief section should render externally generated Markdown as a polished executive brief when configured.

## Projects

Implement `/projects` as the Portfolio dashboard and project selection entry point.

Project selector must include:

- All Projects
- individual projects

Implement:

- `/projects/all` as aggregated All Projects overview;
- `/projects/:projectKey` as individual project overview;
- `/projects/:projectKey/meetings`;
- `/projects/:projectKey/field-operations`;
- `/projects/:projectKey/cost-time`.

For All Projects, implement equivalent aggregated tabs:

- `/projects/all/meetings`;
- `/projects/all/field-operations`;
- `/projects/all/cost-time`.

## Project Overview sections

Use assistant-like dashboard sections:

- Important Today
- What Changed
- Action Items
- Meetings Needing Prep
- Cost & Time Signals
- Field Operations Signals
- Documents / Correspondence Highlights
- Startup / Closeout / Billing Attention, where applicable

## Project secondary tabs

- Meetings
- Field Operations
- Cost & Time

Field Operations must be the location for startup, closeout, daily log, observations, punch-list, inspections, quality/safety, and superintendent-facing data.

Cost & Time must be the location for cost/change, billing/cash/retention, schedule, procurement, and cost/time-impacting RFI/submittal/design-decision signals.

## My Items

Implement `/my-items` as a user-specific dashboard.

Sections:

- My Action Items
- My Meetings
- My Correspondence
- My Files
- My Followed Projects

My Items should be a filtered work queue, not a replacement email client, calendar, or file browser.

## Requirements

- Avoid dry-run/apply/execute terminology.
- Use business-language actions.
- Keep actions low-friction.
- Provide compact freshness/confidence badges.
- Link technical diagnostics to Admin / Data Confidence.
- Do not activate chat.
