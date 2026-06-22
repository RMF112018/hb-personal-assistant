import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleQualityPage } from './ScheduleQualityPage'

const getScheduleQualityMock = vi.fn()
const getScheduleVersionsMock = vi.fn()
const rerunScheduleQualityMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleQuality: (...args: unknown[]) => getScheduleQualityMock(...args),
      getScheduleVersions: (...args: unknown[]) => getScheduleVersionsMock(...args),
      rerunScheduleQuality: (...args: unknown[]) => rerunScheduleQualityMock(...args),
    },
    getLocalUiRole: () => 'operator' as const,
  }
})

function renderPage(version = 'tropical|TWNU18|2026-05-26T08:00:00') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/schedules/quality', element: <ScheduleQualityPage /> }],
    { initialEntries: [`/schedules/quality?version=${encodeURIComponent(version)}`] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ScheduleQualityPage', () => {
  beforeEach(() => {
    getScheduleQualityMock.mockReset()
    getScheduleVersionsMock.mockReset()
    rerunScheduleQualityMock.mockReset()
    getScheduleVersionsMock.mockResolvedValue([
      {
        schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
        display_label: 'TWNU18',
        activity_count: 1378,
      },
    ])
  })

  it('renders disclaimer and DCMA metrics grid', async () => {
    getScheduleQualityMock.mockResolvedValue({
      schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
      status: 'completed',
      assessment_profile: 'dcma_14_point_plus_gao',
      quality_score: '72',
      quality_grade: 'C',
      disclaimer:
        'Schedule quality metrics are deterministic CPM data checks for operator review. This is not forensic delay analysis.',
      scorecard: { dcma_measured_count: 10, dcma_not_measurable_count: 4 },
      metrics: [
        {
          metric_family: 'dcma',
          metric_code: 'dcma_missing_logic',
          metric_name: 'Missing logic',
          value: 0.02,
          unit: 'ratio',
          threshold_warning: 0.05,
          threshold_fail: 0.1,
          status: 'passed_threshold',
          not_measurable_reason: null,
        },
        {
          metric_family: 'dcma',
          metric_code: 'dcma_cpli',
          metric_name: 'CPLI',
          status: 'not_measurable_missing_data',
          not_measurable_reason: 'baseline_schedule_not_available',
        },
      ],
      gao_category_summary: {
        logic_integrity: { posture: 'acceptable', reason: null },
      },
      downstream_readiness: {
        cost_mapping_ready: true,
        cost_weighting_ready: true,
        blockers: [],
      },
      top_findings: [],
    })

    renderPage()

    expect(await screen.findByText('Missing logic')).toBeInTheDocument()
    expect(screen.getByText(/DCMA 14-point metrics/i)).toBeInTheDocument()
    expect(screen.getByText('not_measurable_missing_data')).toBeInTheDocument()
    expect(screen.getByText('baseline_schedule_not_available')).toBeInTheDocument()
    expect(screen.getByText(/logic integrity/i)).toBeInTheDocument()
    expect(screen.getByText(/Cost weighting: ready/i)).toBeInTheDocument()
    expect(screen.getByText(/not forensic delay analysis/i)).toBeInTheDocument()
  })

  it('shows pending state hint when no DCMA metrics yet', async () => {
    getScheduleQualityMock.mockResolvedValue({
      status: 'pending',
      assessment_profile: 'dcma_14_point_plus_gao',
      metrics: [],
      disclaimer: 'Operator review only.',
    })

    renderPage()

    expect(await screen.findByText(/No DCMA metrics yet/i)).toBeInTheDocument()
    expect(screen.getByText(/Refresh status/i)).toBeInTheDocument()
  })
})