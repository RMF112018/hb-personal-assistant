import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, Navigate, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleImportsPage } from './ScheduleImportsPage'
import { ScheduleVersionsPage } from './ScheduleVersionsPage'
import { ScheduleActivitiesPage } from './ScheduleActivitiesPage'
import { ScheduleCostMappingPage } from './ScheduleCostMappingPage'
import { ScheduleQualityPage } from './ScheduleQualityPage'
import { ScheduleIdentityReviewPage } from './ScheduleIdentityReviewPage'
import { ScheduleVersionDiffPage } from './ScheduleVersionDiffPage'
import { ScheduleCostWeightingPage } from './ScheduleCostWeightingPage'
import { ForecastSubnav } from '../components/forecast/ForecastPageChrome'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (opts: { queryKey: unknown[] }) => useQueryMock(opts),
  }
})

function renderRoute(path: string, element: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path, element }], { initialEntries: [path] })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('Schedule routes', () => {
  beforeEach(() => {
    useQueryMock.mockImplementation(() => ({
      data: [],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }))
  })

  it('renders imports under /schedules/imports', () => {
    renderRoute('/schedules/imports', <ScheduleImportsPage />)
    expect(screen.getByRole('heading', { name: /Schedule imports/i })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /Schedule Intelligence sections/i })).toBeInTheDocument()
    expect(screen.getByText(/max 50 MB/i)).toBeInTheDocument()
  })

  it('renders versions under /schedules/versions', () => {
    renderRoute('/schedules/versions', <ScheduleVersionsPage />)
    expect(screen.getByRole('heading', { name: /Schedule versions/i })).toBeInTheDocument()
  })

  it('renders activities under /schedules/activities', () => {
    renderRoute('/schedules/activities', <ScheduleActivitiesPage />)
    expect(screen.getByRole('heading', { name: /Schedule activities/i })).toBeInTheDocument()
  })

  it('renders cost mapping under /schedules/cost-mapping', () => {
    renderRoute('/schedules/cost-mapping', <ScheduleCostMappingPage />)
    expect(screen.getByRole('heading', { name: /Cost mapping/i })).toBeInTheDocument()
  })

  it('renders Schedule Health under /schedules/quality', () => {
    renderRoute('/schedules/quality', <ScheduleQualityPage />)
    expect(screen.getByRole('heading', { name: /Schedule Health/i })).toBeInTheDocument()
  })

  it('renders Schedule Health under /schedules/health', () => {
    renderRoute('/schedules/health', <ScheduleQualityPage />)
    expect(screen.getByRole('heading', { name: /Schedule Health/i })).toBeInTheDocument()
  })

  it('renders identity review under /schedules/identity-review', () => {
    renderRoute('/schedules/identity-review', <ScheduleIdentityReviewPage />)
    expect(screen.getByRole('heading', { name: /Identity Review/i })).toBeInTheDocument()
  })

  it('renders version diff under /schedules/version-diff', () => {
    renderRoute('/schedules/version-diff', <ScheduleVersionDiffPage />)
    expect(screen.getByRole('heading', { name: /Version diff/i })).toBeInTheDocument()
  })

  it('renders cost weighting under /schedules/cost-weighting', () => {
    renderRoute('/schedules/cost-weighting', <ScheduleCostWeightingPage />)
    expect(screen.getByRole('heading', { name: /Cost weighting/i })).toBeInTheDocument()
  })

  it('redirects legacy /forecasting/schedules/imports to /schedules/imports', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/forecasting/schedules/imports',
          element: <Navigate to="/schedules/imports" replace />,
        },
        { path: '/schedules/imports', element: <ScheduleImportsPage /> },
      ],
      { initialEntries: ['/forecasting/schedules/imports'] },
    )
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    expect(screen.getByRole('heading', { name: /Schedule imports/i })).toBeInTheDocument()
  })

  it('forecasting subnav does not include Schedules', () => {
    const router = createMemoryRouter(
      [{ path: '/forecasting', element: <ForecastSubnav /> }],
      { initialEntries: ['/forecasting'] },
    )
    render(<RouterProvider router={router} />)
    expect(screen.queryByRole('link', { name: /Schedules/i })).not.toBeInTheDocument()
  })
})
