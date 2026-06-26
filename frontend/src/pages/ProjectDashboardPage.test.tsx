import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectDashboardPage } from './ProjectDashboardPage'
import { ProjectExposuresPlaceholderPage } from './ProjectExposuresPlaceholderPage'
import { ProjectForecastingPlaceholderPage } from './ProjectForecastingPlaceholderPage'
import { ProjectOverviewPage } from './ProjectOverviewPage'
import { ProjectStaffingPlaceholderPage } from './ProjectStaffingPlaceholderPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown }) => useQueryMock(options),
}))

const projectsResponse = {
  surface: 'analytics.projects.list',
  projects: [
    {
      project_key: 'tropical',
      procore_project_id: '2525840',
      display_name: 'Tropical Resort',
      address: '123 Main St',
      city: 'West Palm Beach',
      state_code: 'FL',
      zip: '33401',
      project_number: 'PR-001',
    },
    {
      project_key: 'key-only',
      display_name: '',
      state_code: 'FL',
      zip: '33480',
    },
  ],
  guardrails: { read_only: true },
}

const legacyOverview = {
  summary: 'Legacy aggregate overview.',
  freshness: { overall: 'fresh', minutes_ago_max: 8 },
  confidence_summary: { overall: 'source_backed' },
  project_count: 2,
  important_today: [{ title: 'Aggregate issue' }],
}

function renderProjectRoutes(path = '/projects/tropical') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects" element={<div>Projects list</div>} />
        <Route path="/projects/all" element={<ProjectDashboardPage />} />
        <Route path="/projects/:projectKey" element={<ProjectOverviewPage />} />
        <Route path="/projects/:projectKey/forecasting" element={<ProjectForecastingPlaceholderPage />} />
        <Route path="/projects/:projectKey/staffing" element={<ProjectStaffingPlaceholderPage />} />
        <Route path="/projects/:projectKey/exposures" element={<ProjectExposuresPlaceholderPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function mockProjectQueries() {
  useQueryMock.mockImplementation((options: { queryKey: unknown[] }) => {
    if (options.queryKey[0] === 'projects') {
      return {
        data: projectsResponse,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    if (options.queryKey[0] === 'project') {
      return {
        data: legacyOverview,
        isLoading: false,
        error: null,
      }
    }
    return {
      data: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }
  })
}

describe('Project workspace shell', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    mockProjectQueries()
  })

  it('renders the selected project shell, identity, metadata, nav, and overview placeholder', () => {
    renderProjectRoutes('/projects/tropical')

    expect(screen.getByText('Project workspace')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Tropical Resort' })).toBeInTheDocument()
    expect(screen.getByText('123 Main St · West Palm Beach, FL 33401')).toBeInTheDocument()
    expect(screen.getByText('Project number')).toBeInTheDocument()
    expect(screen.getByText('PR-001')).toBeInTheDocument()
    expect(screen.getByText('Project key')).toBeInTheDocument()
    expect(screen.getByText('tropical')).toBeInTheDocument()
    expect(screen.getByText('Procore project ID')).toBeInTheDocument()
    expect(screen.getByText('2525840')).toBeInTheDocument()

    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/projects/tropical')
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Forecasting' })).toHaveAttribute('href', '/projects/tropical/forecasting')
    expect(screen.getByRole('link', { name: 'Staffing' })).toHaveAttribute('href', '/projects/tropical/staffing')
    expect(screen.getByRole('link', { name: 'Exposures' })).toHaveAttribute('href', '/projects/tropical/exposures')

    expect(screen.getByRole('heading', { name: 'Project Overview' })).toBeInTheDocument()
    expect(screen.getByText('Financial summary')).toBeInTheDocument()
    expect(screen.getByText('Schedule status')).toBeInTheDocument()
    expect(screen.getByText('Open items')).toBeInTheDocument()
    expect(screen.getByText('Recent activity')).toBeInTheDocument()
  })

  it('falls back to project key and handles partial address fields', () => {
    renderProjectRoutes('/projects/key-only')

    expect(screen.getByRole('heading', { name: 'key-only' })).toBeInTheDocument()
    expect(screen.getByText('FL 33480')).toBeInTheDocument()
  })

  it('uses exact active state for overview and child tabs', () => {
    renderProjectRoutes('/projects/tropical/forecasting')

    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'Forecasting' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('heading', { name: 'Forecasting' })).toBeInTheDocument()
    expect(screen.getByText('Project-specific forecasting will be added here in the next phase.')).toBeInTheDocument()
  })

  it('renders staffing and exposures placeholders under the same shell', () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={['/projects/tropical/staffing']}>
        <Routes>
          <Route path="/projects/:projectKey/staffing" element={<ProjectStaffingPlaceholderPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Tropical Resort' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Staffing' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('heading', { name: 'Staffing' })).toBeInTheDocument()
    expect(screen.getByText('Project staffing configuration and review tools will be added here in a future phase.')).toBeInTheDocument()

    unmount()

    render(
      <MemoryRouter initialEntries={['/projects/tropical/exposures']}>
        <Routes>
          <Route path="/projects/:projectKey/exposures" element={<ProjectExposuresPlaceholderPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Exposures' })).toBeInTheDocument()
    expect(screen.getByText('Project-level exposure tracking will be added here in a future phase.')).toBeInTheDocument()
  })

  it('keeps /projects/all on the legacy aggregate route instead of treating all as a project key', () => {
    renderProjectRoutes('/projects/all')

    expect(screen.getByText('Legacy aggregate overview.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Meetings' })).toHaveAttribute('href', '/projects/all/meetings')
    expect(screen.queryByText('Project not found')).not.toBeInTheDocument()
    expect(screen.queryByText('The selected project could not be found in the local project list.')).not.toBeInTheDocument()
  })

  it('renders a clean not-found state for unknown project keys', () => {
    renderProjectRoutes('/projects/unknown')

    expect(screen.getByText('Project not found')).toBeInTheDocument()
    expect(screen.getByText('The selected project could not be found in the local project list.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Projects' })).toHaveAttribute('href', '/projects')
  })

  it('does not call forecast queries for the forecasting placeholder', () => {
    renderProjectRoutes('/projects/tropical/forecasting')

    const queryKeys = useQueryMock.mock.calls.map(([options]) => options.queryKey)
    expect(queryKeys).toEqual([['projects']])
  })

  it('omits forbidden implementation copy from the selected project shell', () => {
    renderProjectRoutes('/projects/tropical')

    const text = document.body.textContent || ''
    for (const forbidden of [
      'read model',
      'procore_ep_projects',
      'projection',
      'JSON',
      'raw payload',
      'source package',
      'stack trace',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })
})
