import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
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

  it('formats XER quality metrics without impossible ratios', async () => {
    getScheduleQualityMock.mockResolvedValue({
      schedule_version_key: 'tropical|1069|2026-05-26 08:00',
      status: 'completed',
      source_format: 'primavera_xer',
      assessment_profile: 'dcma_14_point_plus_gao',
      metrics: [
        {
          metric_family: 'dcma',
          metric_code: 'dcma_invalid_dates',
          metric_name: 'Invalid dates',
          numerator: 0,
          denominator: 701,
          value: 0,
          unit: 'ratio',
          status: 'passed_threshold',
          evidence_json: JSON.stringify({
            display_mode: 'finding_count',
            total_findings: 0,
            primary_denominator_basis: 'completed_activities',
          }),
        },
        {
          metric_family: 'dcma',
          metric_code: 'dcma_critical_path_test',
          metric_name: 'Critical path test',
          status: 'not_measurable_requires_recalculation',
          not_measurable_reason:
            'CPM recalculation not implemented; source-export flags are not an authoritative DCMA critical path test',
        },
        {
          metric_family: 'supplemental',
          metric_code: 'source_driving_path_integrity_proxy',
          metric_name: 'Source driving path integrity (proxy)',
          numerator: 0,
          denominator: 32,
          status: 'measured_from_source_export_proxy',
          evidence_json: JSON.stringify({
            display_name_override: 'Source driving path integrity (proxy)',
            proxy_violation_count: 0,
            eligible_driving_path_activity_count: 32,
            driving_path_activity_count: 269,
            eligible_denominator_basis: 'driving_path_flag_with_explicit_float',
            method: 'source_export_proxy',
          }),
        },
        {
          metric_family: 'dcma',
          metric_code: 'dcma_relationship_types',
          metric_name: 'Relationship types',
          numerator: 2235,
          denominator: 3718,
          value: 0.6011,
          status: 'passed_threshold',
          evidence_json: JSON.stringify({
            distribution: { FS: 2235, FF: 1357, SS: 125, SF: 1 },
          }),
        },
      ],
      gao_category_summary: {},
      top_findings: [],
    })

    renderPage('tropical|1069|2026-05-26 08:00')

    expect(await screen.findByText('0 findings')).toBeInTheDocument()
    expect(screen.queryByText('1410/1378')).not.toBeInTheDocument()
    expect(screen.getByText(/not_measurable_requires_recalculation/i)).toBeInTheDocument()
    expect(screen.getByText(/Source-export supplemental checks/i)).toBeInTheDocument()
    expect(screen.getByText(/Source driving path integrity \(proxy\)/i)).toBeInTheDocument()
    expect(screen.getByText(/0 violations \/ 32 eligible/i)).toBeInTheDocument()
    expect(screen.getByText(/269 XER driving-path flags/i)).toBeInTheDocument()
    expect(screen.getByText(/not a DCMA critical path test/i)).toBeInTheDocument()
    expect(screen.getByText(/FS 2235 \/ 3718 \(60\.1%\)/i)).toBeInTheDocument()
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