# Frontend UI Structure

## Governing Layout Rule

The application must use a simple, low-friction navigation model. The UI is a construction time-management and data-intelligence platform, not a collection of separate workflow consoles.

Primary top-level navigation:

1. **Today**
2. **Projects**
3. **My Items**

Supporting top-level navigation:

4. **Admin / Data Confidence**
5. **Settings**

No other construction domains should be top-level navigation items in this implementation. Meetings, cost/change, billing/cash, schedule, documents, correspondence, vendors, closeout, field operations, daily logs, observations, punch lists, startup, and closeout data must be surfaced contextually inside Today, Projects, and My Items.

Do not include active Chat navigation. Chat remains future-only and disabled.

---

## Primary Landing: Today

The root route `/` must redirect to `/today`.

The **Today** page is the primary landing page. It is an all-project command-center dashboard that captures high-value information across projects, files, Procore, Outlook/Graph mail, calendar, SharePoint, OneDrive, generated Daily Brief output, and open action items.

The page should answer:

- What matters today?
- What changed?
- What meetings require preparation?
- What decisions are aging?
- What action items need attention?
- What correspondence or documents are worth reviewing?
- Which projects need focus?
- What cost/time/field/closeout signals need review?

### Today Page Sections

Recommended sections:

1. **Important Today**
   - high-priority attention items across all active/followed projects;
   - aging decisions;
   - cost/change exposure signals;
   - schedule/procurement signals;
   - field/closeout/billing attention items;
   - review-required operational items.

2. **Daily Brief**
   - optional executive-style rendered Daily Brief;
   - source is an externally generated Markdown file;
   - show states: Not configured, Configured, Waiting for next run, Brief available, Brief stale, Brief generation failed, External AI setup required;
   - app presents/polishes the Markdown but does not generate or materially rewrite it.

3. **Today’s Meetings**
   - meeting list;
   - prep readiness;
   - related emails/files/Procore context;
   - source/context freshness badge;
   - one-click drilldown to meeting prep view.

4. **What Changed**
   - new/changed Procore records;
   - document/file changes;
   - correspondence highlights;
   - meeting context changes;
   - cost/change/schedule/field signals since last review window.

5. **Action Items**
   - open user-facing items;
   - aging items;
   - review-required items;
   - locally reviewed/unreviewed state;
   - items assigned to or relevant to the current user.

6. **Portfolio Signals**
   - projects needing attention;
   - portfolio cost exposure signals;
   - schedule/procurement signals;
   - closeout/billing/cash attention items;
   - compact confidence/freshness context.

Today should not expose dry-run/apply/execute terminology. Use business language such as Refresh, Review, Prepare, Open, Mark Reviewed, and Update Connection.

---

## Projects

The **Projects** top-level route `/projects` lands on the **Portfolio** dashboard.

Projects is the place for project-centric analytics. It must include a project selector:

- **All Projects**
- individual active/followed projects

### Projects Landing: Portfolio

Default route: `/projects`

The portfolio dashboard should show all-project construction-management analytics:

- projects needing executive attention;
- project health summaries;
- cost/change exposure signals;
- aging RFIs/submittals/design decisions;
- meeting/action burden;
- recent changes by project;
- field operations signals;
- billing/cash/retention attention;
- closeout readiness signals;
- confidence/freshness context as compact support badges.

### All Projects

Route: `/projects/all`

The All Projects view is an aggregated dashboard. It should use the same Project Overview structure but aggregate across projects.

### Individual Project Overview

Route: `/projects/:projectKey`

The selected project landing page is a high-level, project-specific analytics dashboard with assistant-like sections:

- **Important Today**
- **What Changed**
- **Action Items**
- **Meetings Needing Prep**
- **Cost & Time Signals**
- **Field Operations Signals**
- **Documents / Correspondence Highlights**
- **Startup / Closeout / Billing Attention**, where applicable
- compact confidence/freshness badges

### Project-Level Secondary Navigation

Within Projects, use only these secondary tabs:

1. **Overview**
   - route: `/projects/:projectKey`
   - route for all projects: `/projects/all`

2. **Meetings**
   - route: `/projects/:projectKey/meetings`
   - route for all projects: `/projects/all/meetings`
   - uses calendar, Outlook, meeting action items, related files, related Procore context, and Daily Brief/meeting-prep context.

3. **Field Operations**
   - route: `/projects/:projectKey/field-operations`
   - route for all projects: `/projects/all/field-operations`
   - uses startup, closeout, daily logs, observations, punch list, inspections, field issue aging, quality/safety review-required signals, and superintendent-facing attention items.

4. **Cost & Time**
   - route: `/projects/:projectKey/cost-time`
   - route for all projects: `/projects/all/cost-time`
   - uses cost exposure, change management, billing/cash/retention, schedule signals, procurement signals, RFIs/submittals/design decisions where they affect cost/time, budget/commitment/change-event readiness context.

Documents, correspondence, vendors, closeout, billing, schedule, procurement, RFIs, submittals, and design decisions are not standalone top-level nav items. They appear inside these project dashboards and drilldowns.

---

## My Items

Route: `/my-items`

The **My Items** page is a user-centric dashboard. It should show the current user’s filtered work queue and personal data context across Outlook, calendar, OneDrive, action items, followed projects, and review-required items.

The page should answer:

- What is on my plate?
- What meetings do I need to prepare for?
- Which emails are worth reviewing?
- Which OneDrive files matter?
- Which action items or review items need my attention?
- Which followed projects need my attention?

### My Items Sections

1. **My Action Items**
   - open items;
   - aging items;
   - review-required items;
   - locally reviewed/unreviewed state.

2. **My Meetings**
   - today/upcoming meetings;
   - prep status;
   - related files/emails/Procore context.

3. **My Correspondence**
   - emails worth reviewing;
   - stale threads;
   - waiting-on/reply-needed candidates;
   - project-matched and unclassified correspondence.

4. **My Files**
   - OneDrive files;
   - recently changed files;
   - files needing classification/review;
   - files tied to meetings/projects.

5. **My Followed Projects**
   - pinned/followed project summaries;
   - attention items from followed projects.

My Items is not an email client, file browser, or calendar clone. It is a filtered work queue.

---

## Admin / Data Confidence

Route: `/admin`

Admin / Data Confidence is required but secondary. It supports trust, governance, and troubleshooting.

Sections:

- Source / Sync Health
- Workflow / Job Health
- Evidence / Guardrail Health
- Retrieval / AI Quality
- Permissions / Governance
- Data Completeness / Coverage

Operations pages may show compact confidence/freshness badges. Detailed diagnostics belong in Admin / Data Confidence drilldowns.

---

## Settings

Route: `/settings`

Settings should include role-aware controls:

- theme: dark / light / system;
- default landing page: Today, Projects, or My Items;
- pinned/followed projects;
- Daily Brief display preference;
- Daily Brief output folder/file pattern;
- external AI platform setup instructions;
- notification/attention preferences, if implemented;
- project keyword preferences;
- auth reconnect/revoke controls;
- admin-only sync/source/retention controls where applicable.

---

## Disabled Navigation

Chat must remain disabled and not accessible through any active navigation path.

If a route reservation exists, it must expose status only, for example:

- `/api/chat/status` returns disabled/future-only status;
- no `/chat` page;
- no chat nav item;
- no chat widget;
- no streaming endpoint.
