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
      impact_summary: {
        impact_level: 'high',
        requires_attention_count: 7,
        top_wbs_code: 'WBS1',
      },
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

// Phase 9A.3: a fully populated computed_cpm_health envelope (available: true) mirroring the 9A.1
// backend shape, used to exercise the rich Computed CPM Intelligence render.
function computedCpmHealth(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    evidence_class: 'application_computed_cpm',
    source_export_evidence: 'separate',
    run_chain: {
      graph_diagnostics: { available: true, status: 'success', analysis_scope: 'full' },
      forward_pass: { available: true, status: 'success', analysis_scope: 'full' },
      backward_pass: { available: true, status: 'success', analysis_scope: 'full' },
      float: { available: true, status: 'success', analysis_scope: 'full' },
      longest_path: { available: true, status: 'success', analysis_scope: 'full' },
      criticality: { available: true, status: 'success', analysis_scope: 'full' },
    },
    counts: {
      computed_activity_count: 1507,
      computed_critical_activity_count: 87,
      computed_near_critical_activity_count: 142,
      computed_noncritical_activity_count: 1278,
      longest_path_member_count: 87,
      critical_float_threshold_days: 0,
      near_critical_float_threshold_days: 5,
      high_total_float_threshold_days: 44,
    },
    longest_path_summary: {
      available: true,
      path_id: 'PATH001',
      path_type: 'computed',
      activity_count: 87,
      relationship_count: 86,
      path_duration: 845,
      path_total_float: 0,
      start_activity_id: 'A1000',
      end_activity_id: 'A9999',
    },
    dcma_critical_path_metric: {
      available: true,
      measurable: true,
      basis: 'application_computed_cpm',
      caveats: ['computed_critical_outside_longest_path'],
      computed_critical_activity_count: 87,
      longest_path_critical_activity_count: 75,
    },
    links: { computed_cpm: `/schedules/cpm?version=${encodeURIComponent(versionKey)}` },
    ...overrides,
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
    expect(screen.getByText('Impact vs prior')).toBeInTheDocument()
    expect(screen.getByText(/Attention: 7 \| Top WBS: WBS1/i)).toBeInTheDocument()
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

  it('renders the Computed CPM Intelligence shell with a link when CPM is available', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({
        computed_cpm_health: {
          available: true,
          evidence_class: 'application_computed_cpm',
          source_export_evidence: 'separate',
          run_chain: {
            graph_diagnostics: { available: true, status: 'not_implemented' },
            forward_pass: { available: true },
            backward_pass: { available: true },
            float: { available: true },
            longest_path: { available: true },
            criticality: { available: true },
          },
          links: { computed_cpm: `/schedules/cpm?version=${encodeURIComponent(versionKey)}` },
        },
      }),
    )

    renderPage()

    expect(await screen.findByText('Computed CPM Intelligence')).toBeInTheDocument()
    // Application-computed CPM is explicitly labeled and kept distinct from source-export evidence.
    expect(screen.getByText('Application-computed CPM')).toBeInTheDocument()
    expect(screen.getAllByText('Source-export').length).toBeGreaterThan(0)
    const cpmLink = screen.getByRole('link', { name: 'View Computed CPM' })
    expect(cpmLink).toHaveAttribute('href', expect.stringContaining('/schedules/cpm'))
  })

  it('renders an empty Computed CPM shell without breaking source-export sections', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({
        computed_cpm_health: {
          available: false,
          reason: 'no_computed_cpm',
          evidence_class: 'application_computed_cpm',
          source_export_evidence: 'separate',
        },
      }),
    )

    renderPage()

    expect(await screen.findByText('Computed CPM Intelligence')).toBeInTheDocument()
    expect(screen.getByText(/No application-computed CPM is available/i)).toBeInTheDocument()
    // Existing source-export health still renders.
    expect(screen.getByText('Available Schedule Evidence')).toBeInTheDocument()
  })

  it('renders the rich Computed CPM Intelligence section when computed_cpm_health is available', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({ computed_cpm_health: computedCpmHealth() }),
    )

    renderPage()

    expect(await screen.findByText('Computed CPM Intelligence')).toBeInTheDocument()
    // Computed counts and longest-path evidence render.
    expect(screen.getByText('Computed activities')).toBeInTheDocument()
    expect(screen.getByText('Computed critical')).toBeInTheDocument()
    expect(screen.getByText('Computed near-critical')).toBeInTheDocument()
    expect(screen.getByText('Computed noncritical')).toBeInTheDocument()
    expect(screen.getByText('Computed longest path')).toBeInTheDocument()
    expect(screen.getByText(/A1000 → A9999/)).toBeInTheDocument()
    expect(screen.getByText(/Duration:\s*845 d/)).toBeInTheDocument()
    expect(screen.getByText('DCMA critical-path metric')).toBeInTheDocument()
    expect(screen.getByText(/Availability: Available \| Measurability: Measurable/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View Computed CPM' })).toHaveAttribute(
      'href',
      expect.stringContaining('/schedules/cpm'),
    )
  })

  it('replaces the global "not implemented" CPM copy when computed CPM is available', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({ computed_cpm_health: computedCpmHealth() }),
    )

    renderPage()

    expect(await screen.findByText('Computed CPM Intelligence')).toBeInTheDocument()
    // The global "CPM recalculation: not implemented" banner is overridden.
    expect(screen.queryByText(/CPM recalculation: not implemented/i)).not.toBeInTheDocument()
    expect(screen.getByText(/CPM: Application-computed CPM available/i)).toBeInTheDocument()
    // The Unavailable / Deferred Analysis line no longer marks CPM as deferred.
    expect(screen.getByText(/CPM recalculation: Application-computed CPM available/i)).toBeInTheDocument()
  })

  it('keeps source-export critical-path evidence separate from computed CPM', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({ computed_cpm_health: computedCpmHealth() }),
    )

    renderPage()

    // Both the computed section and the source-export section render, distinctly.
    expect(await screen.findByText('Computed CPM Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Critical Path and Float Evidence')).toBeInTheDocument()
    expect(screen.getAllByText('Application-computed CPM').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Source-export').length).toBeGreaterThan(0)
  })

  it('surfaces computed CPM caveats and does not suppress them', async () => {
    getScheduleHealthDataMock.mockResolvedValue(
      healthData({ computed_cpm_health: computedCpmHealth() }),
    )

    renderPage()

    await screen.findByText('Computed CPM Intelligence')
    // The computed_critical_outside_longest_path caveat is shown, not hidden.
    expect(screen.getByText(/outside the longest path/i)).toBeInTheDocument()
    expect(screen.getByTitle('computed_critical_outside_longest_path')).toBeInTheDocument()
  })

  it('keeps the legacy deferred CPM copy when computed_cpm_health is absent', async () => {
    getScheduleHealthDataMock.mockResolvedValue(healthData())

    renderPage()

    await screen.findByText('Unavailable / Deferred Analysis')
    // The shell section still renders, but reports unavailable (no rich computed render).
    expect(screen.getByText(/No application-computed CPM is available/i)).toBeInTheDocument()
    expect(screen.queryByText('Computed longest path')).not.toBeInTheDocument()
    // CPM stays presented as deferred / not implemented.
    expect(screen.getByText(/CPM recalculation: Deferred/i)).toBeInTheDocument()
    expect(screen.getByText(/CPM recalculation: not implemented/i)).toBeInTheDocument()
  })
})
