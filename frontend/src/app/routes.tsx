import {
  createBrowserRouter,
  RouterProvider,
  Outlet,
  useNavigate,
} from 'react-router-dom'
import { useEffect, useState } from 'react'

import { AppShell } from '../layouts/AppShell'
import { TodayPage } from '../pages/TodayPage'
import { ProjectsPage } from '../pages/ProjectsPage'
import { ProjectDashboardPage } from '../pages/ProjectDashboardPage'
import { ProjectMeetingsPage } from '../pages/ProjectMeetingsPage'
import { ProjectFieldOperationsPage } from '../pages/ProjectFieldOperationsPage'
import { ProjectCostTimePage } from '../pages/ProjectCostTimePage'
import { MyItemsPage } from '../pages/MyItemsPage'
import { AdminDataConfidencePage } from '../pages/AdminDataConfidencePage'
import { SettingsPage } from '../pages/SettingsPage'
import { GetStartedPage } from '../pages/GetStartedPage'
import { fetchOnboardingReadiness } from '../hooks/useOnboardingReadiness'

// Root layout using the required AppShell (provides primary + support nav + header + outlet)
// Prompt D: index is now a readiness-driven StartupRedirect (first_time → /get-started; otherwise → /today).
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
 * - Otherwise (ready/degraded/reauth_required with prior setup) → /today.
 * - Renders a minimal non-flicker loader while deciding to avoid flashing Today for first-timers.
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
          navigate('/today', { replace: true });
        }
      } catch {
        // On any error (backend down, etc.) fail open to today to avoid hard block.
        if (!cancelled) navigate('/today', { replace: true });
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
      },
      {
        path: 'projects',
        element: <ProjectsPage />,
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
        element: <ProjectDashboardPage />,
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
      {
        path: 'my-items',
        element: <MyItemsPage />,
      },
      {
        path: 'admin',
        element: <AdminDataConfidencePage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      // Prompt D — Get Started (first-time + returning reauth entry point). Additive; legacy root paths untouched.
      {
        path: 'get-started',
        element: <GetStartedPage />,
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
