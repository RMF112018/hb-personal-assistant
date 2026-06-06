# Prompt 08 FRONTEND UI KIT AND NAVIGATION

Create the modular Vite/React/TypeScript/Tailwind/shadcn-style UI shell with primary dark/system-aware theme and simplified CM-first navigation.

## Required navigation

Top-level primary navigation:

- Today
- Projects
- My Items

Support navigation:

- Admin / Data Confidence
- Settings

Disabled:

- Chat

Do not create active top-level nav items for:

- Portfolio;
- Meetings;
- Action Items;
- Cost / Change;
- Documents;
- Correspondence;
- Vendors;
- Billing / Cash;
- Closeout;
- Field Operations.

Those are contextual sections/tabs inside Today, Projects, or My Items.

## Required frontend structure

Create a route and component structure equivalent to:

```text
frontend/src/
  app/
    App.tsx
    routes.tsx
    providers.tsx
  layouts/
    AppShell.tsx
    MainNavigation.tsx
    SupportNavigation.tsx
    PageHeader.tsx
  navigation/
    navigationModel.ts
  pages/
    TodayPage.tsx
    ProjectsPage.tsx
    ProjectDashboardPage.tsx
    ProjectMeetingsPage.tsx
    ProjectFieldOperationsPage.tsx
    ProjectCostTimePage.tsx
    MyItemsPage.tsx
    AdminDataConfidencePage.tsx
    SettingsPage.tsx
  components/
    dashboard/
    daily-brief/
    projects/
    my-items/
    admin/
    ui/
```

Actual paths may be adjusted to fit repo conventions, but the hierarchy and intent must be preserved.

## Route requirements

- `/` redirects to `/today`
- `/today`
- `/projects`
- `/projects/all`
- `/projects/all/meetings`
- `/projects/all/field-operations`
- `/projects/all/cost-time`
- `/projects/:projectKey`
- `/projects/:projectKey/meetings`
- `/projects/:projectKey/field-operations`
- `/projects/:projectKey/cost-time`
- `/my-items`
- `/admin`
- `/settings`

No active `/chat` route.

## UX requirements

- Primary theme is dark with dark/light/system support.
- Use modular off-the-shelf free UI components where practical.
- Keep construction-facing labels in primary screens.
- Use compact freshness/confidence badges.
- Hide detailed source/sync/evidence/retrieval diagnostics from primary screens; link to Admin / Data Confidence where needed.
