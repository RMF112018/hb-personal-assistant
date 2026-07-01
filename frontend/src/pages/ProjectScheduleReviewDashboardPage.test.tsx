import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import {
  ProjectScheduleReviewDashboardPage,
  portfolioDashboardForbiddenDomText,
} from './ProjectScheduleReviewDashboardPage'

const getScheduleReviewDashboardMock = vi.fn()
const downloadScheduleReviewDashboardExportMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleReviewDashboard: (...args: unknown[]) => getScheduleReviewDashboardMock(...args),
      downloadScheduleReviewDashboardExport: (...args: unknown[]) =>
        downloadScheduleReviewDashboardExportMock(...args),
    },
  }
})

const dashboardFixture = {
  portfolio_summary: {
    project_count: 2,
    projects_with_schedule: 1,
    projects_without_schedule: 1,
    ready_count: 0,
    degraded_count: 0,
    blocked_count: 1,
    needs_review_count: 1,
    stale_schedule_count: 1,
    operator_action_required_count: 2,
  },
  projects: [
    {
      project_key: 'tropical',
      project_label: 'Tropical Wind',
      schedule_label: 'Update Jul 01, 2026',
      schedule_data_date: '2026-07-01',
      schedule_age_days: 2,
      schedule_staleness_status: 'current',
      analytics_trust_status: 'blocked',
      identity_trust_status: 'review_required',
      cpm_trust_status: 'ready',
      quality_trust_status: 'ready',
      portfolio_status: 'blocked',
      operator_action_required: true,
      ready: false,
      review_status: {
        persisted_item_count: 1,
        preview_cue_count: 0,
        needs_review: 1,
        accepted_for_follow_up: 0,
        dismissed_not_material: 0,
        resolved: 0,
        blocked: 0,
      },
      recommended_next_action: {
        action_key: 'identity_review_required',
        label: 'Identity review required',
        pm_description: 'Confirm schedule identity before relying on comparison or review metrics.',
        primary_link: '/schedules/identity-review?project=tropical',
        priority: 10,
      },
      links: {
        hub: '/projects/tropical/schedule',
        controls: '/projects/tropical/schedule?panel=controls',
        workbench: '/projects/tropical/schedule/workbench',
        import: '/projects/tropical/schedule/import',
        identity_review: '/schedules/identity-review?project=tropical',
      },
    },
    {
      project_key: 'palm',
      project_label: 'Palm Shores',
      schedule_label: null,
      schedule_data_date: null,
      schedule_age_days: null,
      schedule_staleness_status: 'missing',
      analytics_trust_status: 'unavailable',
      identity_trust_status: 'unavailable',
      cpm_trust_status: 'unavailable',
      quality_trust_status: 'unavailable',
      portfolio_status: 'missing',
      operator_action_required: true,
      ready: false,
      review_status: {
        persisted_item_count: 0,
        preview_cue_count: 0,
        needs_review: 0,
        accepted_for_follow_up: 0,
        dismissed_not_material: 0,
        resolved: 0,
        blocked: 0,
      },
      recommended_next_action: {
        action_key: 'schedule_import_needed',
        label: 'Schedule import needed',
        pm_description: 'Import a committed schedule update before schedule review metrics are available.',
        primary_link: '/projects/palm/schedule/import',
        priority: 30,
      },
      links: {
        hub: '/projects/palm/schedule',
        controls: '/projects/palm/schedule?panel=controls',
        workbench: '/projects/palm/schedule/workbench',
        import: '/projects/palm/schedule/import',
        identity_review: '/schedules/identity-review?project=palm',
      },
    },
  ],
  filters: {
    available_statuses: ['ready', 'blocked', 'missing'],
    available_actions: ['identity_review_required'],
  },
}

function renderDashboard(initialEntry = '/projects/all/schedule/review') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      {
        path: '/projects/all/schedule/review',
        element: (
          <QueryClientProvider client={queryClient}>
            <ProjectScheduleReviewDashboardPage />
          </QueryClientProvider>
        ),
      },
      {
        path: '/projects/all',
        element: (
          <QueryClientProvider client={queryClient}>
            <ProjectSubNav projectKey="all" />
          </QueryClientProvider>
        ),
      },
    ],
    { initialEntries: [initialEntry] },
  )
  return render(<RouterProvider router={router} />)
}

describe('ProjectScheduleReviewDashboardPage', () => {
  beforeEach(() => {
    getScheduleReviewDashboardMock.mockReset()
    downloadScheduleReviewDashboardExportMock.mockReset()
    getScheduleReviewDashboardMock.mockResolvedValue(dashboardFixture)
    downloadScheduleReviewDashboardExportMock.mockResolvedValue({
      blob: async () => new Blob(['## Portfolio Schedule Review Status'], { type: 'text/markdown' }),
    })
  })

  it('renders summary cards and project rows', async () => {
    renderDashboard()
    expect(await screen.findByText('Schedule Review Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Total projects')).toBeInTheDocument()
    expect(screen.getByText('Tropical Wind')).toBeInTheDocument()
    expect(screen.getByText('Palm Shores')).toBeInTheDocument()
    expect(screen.getByTestId('portfolio-project-table')).toBeInTheDocument()
  })

  it('requests blocked filter from the API', async () => {
    const user = userEvent.setup()
    renderDashboard()
    await screen.findByText('Tropical Wind')
    await user.click(screen.getByRole('button', { name: 'Blocked' }))
    await waitFor(() => {
      expect(getScheduleReviewDashboardMock).toHaveBeenLastCalledWith({ status: 'blocked' })
    })
  })

  it('renders deep links to hub, controls, workbench, import, and identity review', async () => {
    renderDashboard()
    await screen.findByText('Tropical Wind')
    expect(screen.getAllByRole('link', { name: 'Hub' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Controls' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Workbench' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Import' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Identity review' }).length).toBeGreaterThan(0)
  })

  it('does not render raw technical ids in dom text', async () => {
    const { container } = renderDashboard()
    await screen.findByText('Tropical Wind')
    const text = container.textContent || ''
    expect(portfolioDashboardForbiddenDomText(text)).toBe(false)
    expect(text).not.toContain('import_id')
    expect(text).not.toContain('cpm_run_id')
  })

  it('renders empty state when ready filter has no matches', async () => {
    const user = userEvent.setup()
    getScheduleReviewDashboardMock.mockImplementation(async (opts?: { status?: string | null }) => {
      if (opts?.status === 'ready') {
        return {
          ...dashboardFixture,
          projects: [],
          portfolio_summary: { ...dashboardFixture.portfolio_summary, project_count: 0, ready_count: 0 },
        }
      }
      return dashboardFixture
    })
    renderDashboard()
    await screen.findByText('Tropical Wind')
    await user.click(screen.getByRole('button', { name: 'Ready' }))
    expect(await screen.findByText('All visible projects are clear')).toBeInTheDocument()
  })
})

describe('ProjectSubNav', () => {
  it('renders schedule review dashboard navigation entry', async () => {
    renderDashboard('/projects/all')
    expect(await screen.findByRole('link', { name: 'Schedule Review Dashboard' })).toHaveAttribute(
      'href',
      '/projects/all/schedule/review',
    )
  })
})
