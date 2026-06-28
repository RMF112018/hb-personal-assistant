import {
  createBrowserRouter,
  RouterProvider,
  Outlet,
  useNavigate,
  Navigate,
} from 'react-router-dom'
import { useEffect, useState } from 'react'

import { AppShell } from '../layouts/AppShell'
import { TodayPage } from '../pages/TodayPage'
import { ProjectsPage } from '../pages/ProjectsPage'
import { ProjectDashboardPage } from '../pages/ProjectDashboardPage'
import { ProjectOverviewPage } from '../pages/ProjectOverviewPage'
import { ProjectForecastingPage } from '../pages/ProjectForecastingPage'
import { ProjectMonthlyForecastingPage } from '../pages/ProjectMonthlyForecastingPage'
import { ProjectStaffingPage } from '../pages/ProjectStaffingPage'
import { ProjectExposuresPlaceholderPage } from '../pages/ProjectExposuresPlaceholderPage'
import { ProjectMeetingsPage } from '../pages/ProjectMeetingsPage'
import { ProjectFieldOperationsPage } from '../pages/ProjectFieldOperationsPage'
import { ProjectCostTimePage } from '../pages/ProjectCostTimePage'
import { MyItemsPage } from '../pages/MyItemsPage'
import { ForecastingPage } from '../pages/ForecastingPage'
import { ForecastPackagePage } from '../pages/ForecastPackagePage'
import { ForecastConfigPage } from '../pages/ForecastConfigPage'
import { ForecastConfigEditProposalsPage } from '../pages/ForecastConfigEditProposalsPage'
import { ForecastStaffingTemplatesPage } from '../pages/ForecastStaffingTemplatesPage'
import { ForecastRunCenterPage } from '../pages/ForecastRunCenterPage'
import { ForecastExternalEvalPage } from '../pages/ForecastExternalEvalPage'
import { ForecastRuntimeSettingsPage } from '../pages/ForecastRuntimeSettingsPage'
import { ScheduleImportsPage } from '../pages/ScheduleImportsPage'
import { ScheduleVersionsPage } from '../pages/ScheduleVersionsPage'
import { ScheduleActivitiesPage } from '../pages/ScheduleActivitiesPage'
import { ScheduleActivitiesRedirect } from '../pages/ScheduleActivitiesRedirect'
import { ScheduleCostMappingPage } from '../pages/ScheduleCostMappingPage'
import { ScheduleIdentityReviewPage } from '../pages/ScheduleIdentityReviewPage'
import { ScheduleCpmPage } from '../pages/ScheduleCpmPage'
import { ScheduleQualityPage } from '../pages/ScheduleQualityPage'
import { ScheduleVersionDiffPage } from '../pages/ScheduleVersionDiffPage'
import { ScheduleCostWeightingPage } from '../pages/ScheduleCostWeightingPage'
import { DataHealthPage } from '../pages/DataHealthPage'
import { SettingsPage } from '../pages/SettingsPage'
import { GetStartedPage } from '../pages/GetStartedPage'
import { fetchOnboardingReadiness } from '../hooks/useOnboardingReadiness'

// Root layout using the required AppShell (provides primary + support nav + header + outlet)
// Prompt D: index is now a readiness-driven StartupRedirect (first_time → /get-started; otherwise → /my-dashboard).
// Get Started is intentionally not in PRIMARY_NAV (special auto + direct-link + Settings affordance).
function RootLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}

/**
 * StartupRedirect (Prompt D)
 * - On mount fetches /api/onboarding/readiness (plain fetch, no hook).
 * - If onboarding_state === 'first_time' navigates (replace) to /get-started.
 * - Otherwise (ready/degraded/reauth_required with prior setup) → /my-dashboard.
 * - Renders a minimal non-flicker loader while deciding to avoid flashing My Dashboard for first-timers.
 * - Returning stale-auth users with has_prior_setup are sent to main app (panel will surface reauth cards).
 */
function StartupRedirect() {
  const navigate = useNavigate();
  const [deciding, setDeciding] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetchOnboardingReadiness();
        if (cancelled) return;
        if (r && r.onboarding_state === 'first_time') {
          navigate('/get-started', { replace: true });
        } else {
          navigate('/my-dashboard', { replace: true });
        }
      } catch {
        // On any error (backend down, etc.) fail open to my-dashboard to avoid hard block.
        if (!cancelled) navigate('/my-dashboard', { replace: true });
      } finally {
        if (!cancelled) setDeciding(false);
      }
    })();
    return () => { cancelled = true; };
  }, [navigate]);

  if (deciding) {
    return (
      <div className="text-sm text-[var(--hb-muted)] p-4">Checking your local setup…</div>
    );
  }
  return null;
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <StartupRedirect />,
      },
      {
        path: 'today',
        element: <TodayPage />,
        handle: { title: 'Today' },
      },
      {
        path: 'projects',
        element: <ProjectsPage />,
        handle: { title: 'Projects' },
      },
      {
        path: 'projects/all',
        element: <ProjectDashboardPage />, // aggregated "all"
      },
      {
        path: 'projects/all/meetings',
        element: <ProjectMeetingsPage />,
      },
      {
        path: 'projects/all/field-operations',
        element: <ProjectFieldOperationsPage />,
      },
      {
        path: 'projects/all/cost-time',
        element: <ProjectCostTimePage />,
      },
      {
        path: 'projects/:projectKey',
        element: <ProjectOverviewPage />,
      },
      {
        path: 'projects/:projectKey/forecasting',
        element: <ProjectForecastingPage />,
      },
      {
        path: 'projects/:projectKey/forecasting/monthly',
        element: <ProjectMonthlyForecastingPage />,
      },
      {
        path: 'projects/:projectKey/staffing',
        element: <ProjectStaffingPage />,
      },
      {
        path: 'projects/:projectKey/exposures',
        element: <ProjectExposuresPlaceholderPage />,
      },
      {
        path: 'projects/:projectKey/meetings',
        element: <ProjectMeetingsPage />,
      },
      {
        path: 'projects/:projectKey/field-operations',
        element: <ProjectFieldOperationsPage />,
      },
      {
        path: 'projects/:projectKey/cost-time',
        element: <ProjectCostTimePage />,
      },
      // Canonical My Dashboard route (renders the former My Items work-queue page content).
      // Legacy /my-items kept below for alias compatibility; title resolver maps both to 'My Dashboard'.
      {
        path: 'my-dashboard',
        element: <MyItemsPage />,
        handle: { title: 'My Dashboard' },
      },
      {
        path: 'my-items',
        element: <MyItemsPage />,
        handle: { title: 'My Items' },
      },
      // Forecasting — read-only package browser (Implementation Phase 1). Additive.
      {
        path: 'forecasting',
        element: <ForecastingPage />,
        handle: { title: 'Forecasting' },
      },
      // Forecast configuration viewer (Implementation Phase 2). Read-only. Declared before
      // the :packageId route so the literal 'config' segment is not captured as a package id.
      {
        path: 'forecasting/config',
        element: <ForecastConfigPage />,
        handle: { title: 'Forecast Configuration' },
      },
      // Forecast Config Edit Proposals (Implementation Phase E). Static segment before :packageId.
      {
        path: 'forecasting/config/proposals',
        element: <ForecastConfigEditProposalsPage />,
        handle: { title: 'Config Edit Proposals' },
      },
      {
        path: 'forecasting/config/staffing-templates',
        element: <ForecastStaffingTemplatesPage />,
        handle: { title: 'Staffing Templates' },
      },
      // Forecast Run Center (Implementation Phase 3). Static segment before :packageId.
      {
        path: 'forecasting/runs',
        element: <ForecastRunCenterPage />,
        handle: { title: 'Forecast Run Center' },
      },
      // External-Forecast Evaluation (Implementation Phase 4). Static segment before :packageId.
      {
        path: 'forecasting/external',
        element: <ForecastExternalEvalPage />,
        handle: { title: 'External Forecast Evaluation' },
      },
      // Forecast Runtime Settings (Implementation Phase 6). Static segment before :packageId.
      {
        path: 'forecasting/runtime',
        element: <ForecastRuntimeSettingsPage />,
        handle: { title: 'Forecast Runtime Settings' },
      },
      // Schedule Intelligence (V62) — first-class module at /schedules/*.
      {
        path: 'schedules',
        element: <Navigate to="/schedules/imports" replace />,
      },
      {
        path: 'schedules/imports',
        element: <ScheduleImportsPage />,
        handle: { title: 'Schedule Imports' },
      },
      {
        path: 'schedules/versions',
        element: <ScheduleVersionsPage />,
        handle: { title: 'Schedule Versions' },
      },
      {
        path: 'schedules/activities',
        element: <ScheduleActivitiesPage />,
        handle: { title: 'Schedule Activities' },
      },
      {
        path: 'schedules/quality',
        element: <ScheduleQualityPage />,
        handle: { title: 'Schedule Health' },
      },
      {
        path: 'schedules/cpm',
        element: <ScheduleCpmPage />,
        handle: { title: 'Computed CPM' },
      },
      {
        path: 'schedules/identity-review',
        element: <ScheduleIdentityReviewPage />,
        handle: { title: 'Schedule Identity Review' },
      },
      {
        path: 'schedules/health',
        element: <ScheduleQualityPage />,
        handle: { title: 'Schedule Health' },
      },
      {
        path: 'schedules/version-diff',
        element: <ScheduleVersionDiffPage />,
        handle: { title: 'Schedule Version Diff' },
      },
      {
        path: 'schedules/cost-mapping',
        element: <ScheduleCostMappingPage />,
        handle: { title: 'Schedule Cost Mapping' },
      },
      {
        path: 'schedules/cost-weighting',
        element: <ScheduleCostWeightingPage />,
        handle: { title: 'Schedule Cost Weighting' },
      },
      // Legacy forecasting-nested schedule routes → /schedules/*.
      {
        path: 'forecasting/schedules/imports',
        element: <Navigate to="/schedules/imports" replace />,
      },
      {
        path: 'forecasting/schedules/versions',
        element: <Navigate to="/schedules/versions" replace />,
      },
      {
        path: 'forecasting/schedules/cost-mapping',
        element: <Navigate to="/schedules/cost-mapping" replace />,
      },
      {
        path: 'forecasting/schedules/versions/:scheduleVersionKey/activities',
        element: <ScheduleActivitiesRedirect />,
      },
      {
        path: 'forecasting/:packageId',
        element: <ForecastPackagePage />,
        handle: { title: 'Forecast Package' },
      },
      {
        path: 'admin',
        element: <DataHealthPage />,
        handle: { title: 'Data Health' },
      },
      {
        path: 'settings',
        element: <SettingsPage />,
        handle: { title: 'Settings' },
      },
      // Prompt D — Get Started (first-time + returning reauth entry point). Additive; legacy root paths untouched.
      {
        path: 'get-started',
        element: <GetStartedPage />,
        handle: { title: 'Get Started' },
      },
      // Explicitly no /chat route or page per requirements.
    ],
  },
  {
    path: '*',
    element: (
      <div className="p-8">
        <h1 className="text-xl">Not found</h1>
        <p className="text-sm text-muted">The page does not exist in this CM-first navigation.</p>
      </div>
    ),
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}

// Also export the router if needed for tests or future
// eslint-disable-next-line react-refresh/only-export-components
export { router }
