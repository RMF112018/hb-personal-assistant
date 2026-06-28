import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleCpmPage } from './ScheduleCpmPage'

const getScheduleCpmSummaryMock = vi.fn()
const getScheduleCpmActivitiesMock = vi.fn()
const getScheduleCpmLongestPathMock = vi.fn()
const getScheduleProjectsMock = vi.fn()
const getScheduleVersionsMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleCpmSummary: (...a: unknown[]) => getScheduleCpmSummaryMock(...a),
      getScheduleCpmActivities: (...a: unknown[]) => getScheduleCpmActivitiesMock(...a),
      getScheduleCpmLongestPath: (...a: unknown[]) => getScheduleCpmLongestPathMock(...a),
      getScheduleProjects: (...a: unknown[]) => getScheduleProjectsMock(...a),
      getScheduleVersions: (...a: unknown[]) => getScheduleVersionsMock(...a),
    },
    getLocalUiRole: () => 'operator' as const,
  }
})

const VERSION = 'tropical|sched|2026-06-01'

function renderPage(path = `/schedules/cpm?project=tropical&version=${encodeURIComponent(VERSION)}`) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path: '/schedules/cpm', element: <ScheduleCpmPage /> }], {
    initialEntries: [path],
  })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

function fullSummary(over: Record<string, unknown> = {}) {
  return {
    schedule_version_key: VERSION,
    available: true,
    runs: {
      graph_diagnostics: { available: true, cpm_recalculation_status: 'not_implemented' },
      forward_pass: { available: true, cpm_recalculation_status: 'forward_pass_only' },
      backward_pass: { available: true, cpm_recalculation_status: 'backward_pass_only' },
      float: { available: true, cpm_recalculation_status: 'forward_backward_float_only' },
      longest_path: { available: true, cpm_recalculation_status: 'longest_path_only' },
      criticality: { available: true, cpm_recalculation_status: 'criticality_classification_only' },
    },
    dcma_critical_path: {
      available: true,
      measurable: true,
      basis: 'application_computed_cpm',
      dependency_run_ids: { forward: 'f', backward: 'b', float: 'fl', longest_path: 'lp', criticality: 'cr' },
      reason_codes: [],
      caveats: [],
      source_critical_flags_used: false,
    },
    missing_dependency_reasons: [],
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getScheduleProjectsMock.mockResolvedValue({ projects: [] })
  getScheduleVersionsMock.mockResolvedValue([])
  getScheduleCpmActivitiesMock.mockResolvedValue({
    schedule_version_key: VERSION,
    available: true,
    source_run: { cpm_run_id: 'cr', calculation_type: 'criticality' },
    activities: [
      {
        activity_id: 'A1000', activity_name: 'Driving Task', computed_early_start: '2026-06-01T00:00:00',
        computed_early_finish: '2026-06-06T00:00:00', computed_total_float: 0, computed_free_float: 0,
        computed_criticality_class: 'computed_critical', longest_path_member_flag: 1, longest_path_sequence: 1,
      },
    ],
    total_count: 1, limit: 1000, offset: 0, truncated: false,
  })
  getScheduleCpmLongestPathMock.mockResolvedValue({
    schedule_version_key: VERSION,
    available: true,
    path: { path_id: 'p1', path_type: 'longest_path', start_activity_id: 'A1000', end_activity_id: 'A1010', activity_count: 2, path_duration: 15 },
    activities: [
      { activity_id: 'A1000', activity_name: 'Driving Task', longest_path_sequence: 1, computed_total_float: 0, computed_criticality_class: 'computed_critical' },
      { activity_id: 'A1010', activity_name: 'Float Task', longest_path_sequence: 2, computed_total_float: 0, computed_criticality_class: 'computed_critical' },
    ],
  })
})

describe('ScheduleCpmPage', () => {
  it('renders empty state when no computed CPM is available', async () => {
    getScheduleCpmSummaryMock.mockResolvedValue({
      schedule_version_key: VERSION, available: false, runs: {},
      dcma_critical_path: { available: false, measurable: false }, missing_dependency_reasons: ['forward_pass'],
    })
    renderPage()
    expect(await screen.findByText(/No computed CPM yet/i)).toBeInTheDocument()
  })

  it('renders the run chain card with all run statuses', async () => {
    getScheduleCpmSummaryMock.mockResolvedValue(fullSummary())
    renderPage()
    expect(await screen.findByText('CPM run chain')).toBeInTheDocument()
    for (const label of ['Graph diagnostics', 'Forward pass', 'Backward pass', 'Float', 'Longest path', 'Criticality']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('DCMA card distinguishes application-computed CPM from source-export evidence', async () => {
    getScheduleCpmSummaryMock.mockResolvedValue(fullSummary())
    renderPage()
    expect(await screen.findByText(/Application-computed CPM available/i)).toBeInTheDocument()
    expect(screen.getByText(/based on application-computed CPM evidence/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Source-export evidence is shown separately/i).length).toBeGreaterThan(0)
  })

  it('labels the path as Longest Path, not Critical Path', async () => {
    getScheduleCpmSummaryMock.mockResolvedValue(fullSummary())
    renderPage()
    expect(await screen.findByText('Longest path')).toBeInTheDocument()
    expect(screen.queryByText(/Critical Path/i)).not.toBeInTheDocument()
  })

  it('renders ordered longest-path activities and computed activity fields', async () => {
    getScheduleCpmSummaryMock.mockResolvedValue(fullSummary())
    renderPage()
    expect(await screen.findByText('Computed activities')).toBeInTheDocument()
    expect(screen.getAllByText('Driving Task').length).toBeGreaterThan(0)
    expect(screen.getByText('Float Task')).toBeInTheDocument()
  })

  it('renders missing-dependency reasons', async () => {
    getScheduleCpmSummaryMock.mockResolvedValue(
      fullSummary({ missing_dependency_reasons: ['criticality'] }),
    )
    renderPage()
    expect(await screen.findByText(/Missing: criticality/i)).toBeInTheDocument()
  })

  it('renders an error state when the summary request fails', async () => {
    getScheduleCpmSummaryMock.mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText(/Could not load computed CPM/i)).toBeInTheDocument()
  })
})
