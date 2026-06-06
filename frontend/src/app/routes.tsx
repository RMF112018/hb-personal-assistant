import {
  createBrowserRouter,
  RouterProvider,
  Navigate,
  Outlet,
} from 'react-router-dom'

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

// Root layout using the required AppShell (provides primary + support nav + header + outlet)
function RootLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/today" replace />,
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

// eslint-disable-next-line react-refresh/only-export-components
export function AppRouter() {
  return <RouterProvider router={router} />
}

// Also export the router if needed for tests or future
export { router }
