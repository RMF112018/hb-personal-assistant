import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleQualityPage } from './ScheduleQualityPage'

const getScheduleHealthDataMock = vi.fn()
const getScheduleQualityMock = vi.fn()
const getScheduleProjectsMock = vi.fn()
const getScheduleVersionsMock = vi.fn()
const rerunScheduleQualityMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleHealthData: (...args: unknown[]) => getScheduleHealthDataMock(...args),
      getScheduleQuality: (...args: unknown[]) => getScheduleQualityMock(...args),
      getScheduleProjects: (...args: unknown[]) => getScheduleProjectsMock(...args),
      getScheduleVersions: (...args: unknown[]) => getScheduleVersionsMock(...args),
      rerunScheduleQuality: (...args: unknown[]) => rerunScheduleQualityMock(...args),
    },
    getLocalUiRole: () => 'operator' as const,
  }
})

const versionKey = 'twn|1071|2026-06-23 08:00'

function renderPage(path = `/schedules/quality?project=twn&version=${encodeURIComponent(versionKey)}`) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/schedules/quality', element: <ScheduleQualityPage /> },
      { path: '/schedules/health', element: <ScheduleQualityPage /> },
    ],
    { initialEntries: [path] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

function capability(capability_key: string, capability_status = 'available') {
  return {
    capability_id: `cap-${capability_key}`,
    capability_key,
    capability_status,
    basis: 'package_manifest',
  }
}

function healthData(overrides: Record<string, unknown> = {}) {
  return {
    schedule_version_key: versionKey,
    project_key: 'twn',
    current_schedule: {
      schedule_version_key: versionKey,
      display_label: 'TWNU19',
      source_format: 'primavera_xer',
      source_type: 'xer',
      imported_at: '2026-06-26 09:41:15',
      activity_count: 1507,
      relationship_count: 3921,
    },
    import_package: {
      package_id: 'pkg-1',
      package_mode: 'zip_package',
      selected_current_project_name: 'TWNU19',
    },
    capabilities: [
      capability('current_activity_rows'),
      capability('current_relationship_rows'),
      capability('baseline_project_rows'),
      capability('baseline_activity_rows'),
      capability('baseline_drift'),
      capability('default_version_diff', 'partially_available'),
      capability('source_critical_path'),
      capability('explicit_total_float'),
      capability('cpm_recalculation', 'deferred'),
      capability('cost_schedule_correlation', 'deferred'),
    ],
    quality_summary: {
      status: 'completed',
      scorecard: {
        quality_score: '72.2',
        quality_grade: 'C',
        dcma_measured_count: 9,
        dcma_not_measurable_count: 5,
        finding_counts_json: JSON.stringify({ critical: 0, warning: 19 }),
        downstream_readiness_json: JSON.stringify({
          completion_posture: 'completed_with_limitations',
          critical_path_analytics: 'available_source_export_only',
          cpm_recalculation: 'not_implemented',
        }),
        gao_category_summary_json: JSON.stringify({
          critical_path_validity: {
            posture: 'partial',
            reason: 'source-export critical path evidence is present but CPM recalculation is required',
          },
        }),
      },
    },
    default_version_diff: [
      {
        fact_id: 'diff-activity-changed',
        metric_key: 'activity_changed_count',
        metric_value: '12',
        status: 'available',
        basis: 'default_prior_version',
      },
    ],
    available_version_diffs: [
      {
        diff_id: 'diff-1',
        from_schedule_version_key: 'twn|1069|2026-05-26 08:00',
      },
    ],
    comparison_basis: {
      current_schedule_identity_key: 'identity-current',
      default_prior_schedule_version_key: 'twn|1069|2026-05-26 08:00',
      default_prior_schedule_identity_key: 'identity-current',
      default_prior_selection_reason: 'persisted_default_diff',
      default_prior_available: true,
      identity_match_type: 'exact_activity_fingerprint',
      identity_confidence_score: '1.00',
      identity_requires_review: false,
      identity_safe: true,
    },
    baseline_projects: [
      {
        baseline_project_key: 'bl-1',
        baseline_project_name: 'Tropical World Nursery - U18',
        baseline_type_name: 'Last Performance Update',
        baseline_data_date: '2026-05-26T08:00:00',
        activity_count: 1378,
        relationship_count: 3718,
      },
    ],
    baseline_health_facts: [
      {
        fact_id: 'baseline-drift',
        baseline_project_key: 'bl-1',
        metric_key: 'baseline_drift_status',
        metric_value: 'measurable_by_crosswalk',
        status: 'available',
      },
    ],
    top_health_findings: [
      {
        severity: 'warning',
        finding_code: 'dcma_negative_float',
        category: 'float_reasonableness',
        finding_summary: 'Negative float exceeds threshold',
        activity_id: 'A1000',
      },
    ],
    deferred_domains: { cost_schedule_correlation: 'deferred' },
    ...overrides,
  }
}

function qualityDetail() {
  return {
    status: 'completed',
    source_format: 'primavera_xer',
    metrics: [
      {
        metric_family: 'dcma',
        metric_code: 'dcma_relationship_types',
        metric_name: 'Relationship types',
        numerator: 2235,
        denominator: 3718,
        value: 0.6011,
        unit: 'ratio',
        status: 'passed_threshold',
        evidence_json: JSON.stringify({ distribution: { FS: 2235, FF: 1357, SS: 125, SF: 1 } }),
      },
      {
        metric_family: 'source_export',
        metric_code: 'source_critical_path_available',
        metric_name: 'Source critical path available',
        numerator: 711,
        status: 'available_xer_total_float_threshold',
        evidence_json: JSON.stringify({
          source_critical_basis: 'xer_total_float_threshold',
          source_critical_path_type: 'CT_TotFloat',
          source_critical_activity_count: 711,
          source_driving_path_count: 327,
          explicit_float_activity_count: 712,
          driving_path_with_explicit_float_count: 27,
          activity_count: 1507,
          source_critical_float_threshold_hours: 0,
        }),
      },
    ],
    gao_category_summary: {},
    top_findings: [],
  }
}

describe('ScheduleQualityPage as Schedule Health', () => {
  beforeEach(() => {
    getScheduleHealthDataMock.mockReset()
    getScheduleQualityMock.mockReset()
    getScheduleProjectsMock.mockReset()
    getScheduleVersionsMock.mockReset()
    rerunScheduleQualityMock.mockReset()
    getScheduleProjectsMock.mockResolvedValue({ projects: [{ project_key: 'twn', display_name: 'TWN' }] })
    getScheduleVersionsMock.mockResolvedValue([
      { schedule_version_key: versionKey, display_label: 'TWNU19', activity_count: 1507 },
    ])
    getScheduleQualityMock.mockResolvedValue(qualityDetail())
  })

  it('renders Schedule Health from /schedules/quality using health-data', async () => {
    getScheduleHealthDataMock.mockResolvedValue(healthData())

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Schedule Health' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Schedule Health/i })).toBeInTheDocument()
    expect(await screen.findByText('Available Schedule Evidence')).toBeInTheDocument()
    expect(screen.getByText('What Changed Since the Prior Schedule?')).toBeInTheDocument()
    expect(screen.getByText('Baseline Health')).toBeInTheDocument()
    expect(screen.getByText('Critical Path and Float Evidence')).toBeInTheDocument()
    expect(screen.getByText('Unavailable / Deferred Analysis')).toBeInTheDocument()
    expect(screen.getByText(/Tropical World Nursery - U18/i)).toBeInTheDocument()
    expect(screen.getByText(/Cost\/schedule correlation: Deferred/i)).toBeInTheDocument()
    expect(getScheduleHealthDataMock).toHaveBeenCalledWith(versionKey, 'twn')
  })

  it('renders the /schedules/health alias as the same Schedule Health page', async () => {
    getScheduleHealthDataMock.mockResolvedValue(healthData())

    renderPage(`/schedules/health?project=twn&version=${encodeURIComponent(versionKey)}`)

    expect(await screen.findByRole('heading', { name: 'Schedule Health' })).toBeInTheDocument()
    expect(await screen.findByText('Available Schedule Evidence')).toBeInTheDocument()
  })

  it('shows XER-only baseline reference as limited, not failed', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({
        baseline_projects: [],
        baseline_health_facts: [],
        capabilities: [
          capability('current_activity_rows'),
          capability('baseline_activity_rows', 'requires_companion_file'),
          capability('source_critical_path'),
          capability('cpm_recalculation', 'deferred'),
          capability('cost_schedule_correlation', 'deferred'),
        ],
      }),
    )

    renderPage()

    expect((await screen.findAllByText(/Baseline reference detected/i)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Requires companion file/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/failed/i)).not.toBeInTheDocument()
  })

  it('renders old imports without package metadata as limited health data', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({
        import_package: {},
        capabilities: [],
        baseline_projects: [],
        baseline_health_facts: [],
        default_version_diff: [],
        available_version_diffs: [],
      }),
    )

    renderPage()

    expect(await screen.findByText(/Limited health data available/i)).toBeInTheDocument()
    expect(screen.getByText(/Re-import using the package-aware workflow/i)).toBeInTheDocument()
  })
})
