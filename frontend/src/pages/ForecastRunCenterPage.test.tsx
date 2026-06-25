import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastRunCenterPage } from './ForecastRunCenterPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const startDbConfigMock = vi.fn().mockResolvedValue({})

vi.mock('../lib/api', () => ({
  api: {
    getForecastRuns: vi.fn(),
    getForecastDbConfigRuns: vi.fn(),
    getForecastGenerationReadiness: vi.fn(),
    getForecastDbConfigRun: vi.fn(),
    getForecastRun: vi.fn(),
    startForecastRun: vi.fn().mockResolvedValue({}),
    startForecastDbConfigRun: (...args: unknown[]) => startDbConfigMock(...args),
    getForecastDbProjects: vi.fn(),
    getForecastGenerationProjects: vi.fn(),
    getForecastGenerationRequests: vi.fn(),
    getForecastGenerationDateDefaults: vi.fn(),
    getForecastDbOutputs: vi.fn(),
    getForecastDbNarratives: vi.fn(),
    getForecastDbDecisionSupport: vi.fn(),
    getForecastOperatorAssumptions: vi.fn(),
    getForecastRequiredAssumptions: vi.fn(),
  },
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
    const kind = opts.queryKey[1]
    const sub = opts.queryKey[2]
    if (kind === 'generation' && sub === 'date-defaults') {
      // Default mock: no schedule-derived defaults (auto-fill fills nothing) so generation-call
      // assertions stay stable. P-D value cases install their own mock below.
      return {
        data: {
          project_key: 'tropical',
          forecast_start_date: null,
          forecast_start_date_basis: null,
          forecast_cutoff_date: null,
          forecast_cutoff_date_basis: null,
          schedule_version_key: null,
          schedule_data_date: null,
          schedule_data_date_basis: null,
          schedule_source_status: 'missing',
          warnings: ['no_schedule_cutoff_default_available'],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    if (kind === 'generation' && sub === 'readiness') {
      return {
        data: {
          generation_enabled: true,
          ready: true,
          disabled_reasons: [],
          warnings: [],
          actions: [],
          guardrails: { read_only: true, no_output_package_generation: true },
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    if (kind === 'generation' && sub === 'projects') {
      return {
        data: {
          surface: 'analytics.forecast_generation_projects',
          generation_enabled: true,
          projects: [
            {
              project_key: 'tropical',
              display_name: 'Tropical Resort',
              project_number: 'PR-001',
              procore_project_id: '9001',
              has_schedule_data: true,
              has_activity_data: true,
              latest_schedule_version_key: null,
              latest_schedule_date: null,
              has_prior_forecast_output: true,
              latest_forecast_status: 'generated',
              latest_forecast_display: 'Jun 19, 2026',
              has_budget_cost_data: true,
              config_snapshot_available: true,
              readiness_status: 'ready',
              readiness_reasons: [],
            },
            {
              project_key: 'harbor',
              display_name: 'Harbor Tower',
              project_number: 'PR-002',
              procore_project_id: '9002',
              has_schedule_data: false,
              has_activity_data: false,
              latest_schedule_version_key: null,
              latest_schedule_date: null,
              has_prior_forecast_output: false,
              latest_forecast_status: null,
              latest_forecast_display: null,
              has_budget_cost_data: false,
              config_snapshot_available: false,
              readiness_status: 'blocked',
              readiness_reasons: ['no_financial_basis'],
              forecast_maturity: 'no_financial_basis',
              confidence_level: 'none',
            },
            {
              project_key: 'summit',
              display_name: 'Summit Center',
              project_number: 'PR-003',
              procore_project_id: '9003',
              has_schedule_data: false,
              has_activity_data: false,
              latest_schedule_version_key: null,
              latest_schedule_date: null,
              has_prior_forecast_output: false,
              latest_forecast_status: null,
              latest_forecast_display: null,
              has_budget_cost_data: true,
              config_snapshot_available: false,
              readiness_status: 'degraded',
              readiness_reasons: ['missing_config_snapshot', 'no_prior_forecast_output'],
              forecast_maturity: 'baseline_only',
              confidence_level: 'low',
              initial_forecast: true,
            },
          ],
          guardrails: { read_only: true },
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    if (kind === 'runs' && sub === 'db-config') {
      return {
        data: {
          runs: [
            {
              run_id: 'db999',
              display_label: 'Comprehensive forecast from live config — Jun 21, 2026 9:00 AM',
              status: 'generated',
              generated_display: 'Jun 21, 2026 9:00 AM',
            },
          ],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    if (kind === 'runs') {
      return {
        data: {
          runs: [
            {
              run_id: 'abc123',
              display_label: 'Context → analysis forecast — Jun 20, 2026 1:07 PM',
              status: 'succeeded',
              generated_display: 'Jun 20, 2026 1:07 PM',
            },
          ],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    // detail query (no selection initially)
    return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastRunCenterPage />
    </MemoryRouter>,
  )
}

describe('ForecastRunCenterPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    startDbConfigMock.mockClear()
  })

  it('renders the primary DB-backed generate action and run history', () => {
    mockData()
    renderPage()
    expect(
      screen.getByRole('button', { name: 'Generate DB-backed forecast' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Generation history')).toBeInTheDocument()
    expect(
      screen.getByText('Context → analysis forecast — Jun 20, 2026 1:07 PM'),
    ).toBeInTheDocument()
  })

  it('renders the live-config generation action and merges both run sources', () => {
    mockData()
    renderPage()
    expect(
      screen.getByRole('button', { name: 'Generate DB-backed forecast' }),
    ).toBeInTheDocument()
    // both a file-config and a live-config run appear, with a Source column distinguishing them
    expect(
      screen.getByText('Comprehensive forecast from live config — Jun 21, 2026 9:00 AM'),
    ).toBeInTheDocument()
    expect(screen.getByText('Live configuration')).toBeInTheDocument()
    expect(screen.getByText('File configuration')).toBeInTheDocument()
  })

  it('describes Generate Forecast as live-config generation without a package/download, and does not promise a DB write it cannot keep', () => {
    mockData()
    const { container } = renderPage()
    const text = container.textContent || ''
    // Honest framing: generates from the promoted live configuration, no package/download.
    expect(text).toMatch(/live configuration/i)
    expect(text).not.toMatch(/isolated forecast package/i)
    // Must NOT imply DB-native generation persists the forecast to the database (backend still
    // returns db_native_generation_not_implemented). No "writes/written … to the … database" promise.
    expect(text).not.toMatch(/writes? the selected project's forecast to the local application database/i)
    expect(text).not.toMatch(/output is written to the local application database/i)
  })

  it('offers all four generator kinds and passes the selected kind + project to the API', async () => {
    mockData()
    renderPage()
    // Generation is gated on an explicit project selection (no tropical fallback).
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    const select = screen.getByLabelText('Forecast type') as HTMLSelectElement
    const optionValues = Array.from(select.options).map((o) => o.value)
    expect(optionValues).toEqual(['comprehensive', 'model_controls', 'monthly', 'probability'])

    fireEvent.change(select, { target: { value: 'monthly' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate DB-backed forecast' }))
    await waitFor(() =>
      expect(startDbConfigMock).toHaveBeenCalledWith({
        project_key: 'tropical',
        generator_kind: 'monthly',
        forecast_start_date: null,
        forecast_cutoff_date: null,
        forecast_cutoff_date_basis: null,
      }),
    )
  })

  it('disables live-config generation and shows actionable reasons before click when not ready', () => {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      const kind = opts.queryKey[1]
      const sub = opts.queryKey[2]
      if (kind === 'generation' && sub === 'readiness') {
        return {
          data: {
            generation_enabled: false,
            ready: false,
            disabled_reasons: [
              'db_config_run_disabled',
              'forecast_runtime_storage_not_configured',
            ],
            warnings: [],
            actions: [
              { code: 'enable_db_config_run', label: 'Enable generation from live configuration' },
              { code: 'open_storage_settings', label: 'Open storage settings' },
            ],
            guardrails: { read_only: true },
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: { runs: [] }, isLoading: false, error: null, refetch: vi.fn() }
    })
    renderPage()

    const button = screen.getByRole('button', { name: 'Generate DB-backed forecast' })
    expect(button).toBeDisabled()
    expect(screen.getByLabelText('Forecast type')).toBeDisabled()
    // Actionable, path-free copy + operator actions are shown BEFORE any click.
    expect(
      screen.getByText("Generating from live configuration isn't enabled in this environment."),
    ).toBeInTheDocument()
    expect(screen.getByText('Forecast storage is not configured yet.')).toBeInTheDocument()
    expect(screen.getByText('Open storage settings')).toBeInTheDocument()
    expect(screen.getByText('Enable generation from live configuration')).toBeInTheDocument()

    // A disabled control cannot start a run.
    fireEvent.click(button)
    expect(startDbConfigMock).not.toHaveBeenCalled()
  })

  it('threads operator-supplied forecast dates into the generation request body', async () => {
    mockData()
    renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    fireEvent.change(screen.getByLabelText('Forecast start date'), {
      target: { value: '2026-06-01' },
    })
    fireEvent.change(screen.getByLabelText('Forecast cut-off date'), {
      target: { value: '2026-06-24' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Generate DB-backed forecast' }))
    await waitFor(() =>
      expect(startDbConfigMock).toHaveBeenCalledWith({
        project_key: 'tropical',
        generator_kind: 'comprehensive',
        forecast_start_date: '2026-06-01',
        forecast_cutoff_date: '2026-06-24',
        forecast_cutoff_date_basis: 'operator_supplied',
      }),
    )
  })

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d{8}_\d{6}/)
    expect(text).not.toMatch(/\/Users\//)
  })

  it('renders the project selector with readiness in option labels', () => {
    mockData()
    renderPage()
    const select = screen.getByLabelText('Forecast project') as HTMLSelectElement
    const labels = Array.from(select.options).map((o) => o.textContent)
    expect(labels).toContain('Select a project')
    expect(labels).toContain('Tropical Resort')
    expect(labels).toContain('Harbor Tower — blocked')
    // A degraded (sparse / first-run) project surfaces its status but is still selectable.
    expect(labels).toContain('Summit Center — degraded')
    // Option values are project keys, not a hardcoded tropical default.
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      '',
      'tropical',
      'harbor',
      'summit',
    ])
  })

  it('disables generation until a non-blocked project is selected, then passes project_key', async () => {
    mockData()
    renderPage()
    const button = () => screen.getByRole('button', { name: 'Generate DB-backed forecast' })
    // Nothing selected → disabled (no tropical fallback).
    expect(button()).toBeDisabled()

    // A blocked project stays disabled and explains why (table-name-free copy).
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'harbor' } })
    expect(button()).toBeDisabled()
    expect(
      screen.getByText('No budget, cost, or baseline data is available to forecast from yet.'),
    ).toBeInTheDocument()

    // A ready project enables generation and threads the selected project_key.
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    expect(button()).not.toBeDisabled()
    fireEvent.click(button())
    await waitFor(() =>
      expect(startDbConfigMock).toHaveBeenCalledWith({
        project_key: 'tropical',
        generator_kind: 'comprehensive',
        forecast_start_date: null,
        forecast_cutoff_date: null,
        forecast_cutoff_date_basis: null,
      }),
    )
  })

  it('allows generation for a degraded (sparse / first-run) project, not just a fully-ready one', async () => {
    mockData()
    renderPage()
    const button = () => screen.getByRole('button', { name: 'Generate DB-backed forecast' })
    // A budget-only first-run project is degraded (limited data), NOT blocked → generation allowed.
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'summit' } })
    expect(button()).not.toBeDisabled()
    fireEvent.click(button())
    await waitFor(() =>
      expect(startDbConfigMock).toHaveBeenCalledWith({
        project_key: 'summit',
        generator_kind: 'comprehensive',
        forecast_start_date: null,
        forecast_cutoff_date: null,
        forecast_cutoff_date_basis: null,
      }),
    )
  })

  function mockWithScheduleDefaults() {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      const kind = opts.queryKey[1]
      const sub = opts.queryKey[2]
      if (kind === 'generation' && sub === 'date-defaults') {
        return {
          data: {
            project_key: 'tropical',
            forecast_start_date: '2025-01-01',
            forecast_start_date_basis: 'earliest_actual_cost_month',
            forecast_cutoff_date: '2026-06-01',
            forecast_cutoff_date_basis: 'schedule_data_date',
            schedule_version_key: 'tropical|S1|2026-06-01',
            schedule_data_date: '2026-06-01',
            schedule_data_date_basis: 'schedule_version_key',
            schedule_source_status: 'available',
            warnings: [],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'readiness') {
        return {
          data: { ready: true, generation_enabled: true, disabled_reasons: [], warnings: [], actions: [], guardrails: {} },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'projects') {
        return {
          data: {
            projects: [
              { project_key: 'tropical', display_name: 'Tropical', readiness_status: 'ready', readiness_reasons: [] },
            ],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: { runs: [] }, isLoading: false, error: null, refetch: vi.fn() }
    })
  }

  it('auto-fills blank dates from schedule defaults and submits the schedule_data_date basis', async () => {
    mockWithScheduleDefaults()
    renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })

    const cutoff = screen.getByLabelText('Forecast cut-off date') as HTMLInputElement
    await waitFor(() => expect(cutoff.value).toBe('2026-06-01'))
    expect((screen.getByLabelText('Forecast start date') as HTMLInputElement).value).toBe('2025-01-01')
    expect(screen.getByText(/Cut-off basis:/)).toHaveTextContent('Schedule data date')

    fireEvent.click(screen.getByRole('button', { name: 'Generate DB-backed forecast' }))
    await waitFor(() =>
      expect(startDbConfigMock).toHaveBeenCalledWith({
        project_key: 'tropical',
        generator_kind: 'comprehensive',
        forecast_start_date: '2025-01-01',
        forecast_cutoff_date: '2026-06-01',
        forecast_cutoff_date_basis: 'schedule_data_date',
      }),
    )
  })

  it('operator override of the defaulted cut-off flips the basis to operator_supplied', async () => {
    mockWithScheduleDefaults()
    renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    const cutoff = screen.getByLabelText('Forecast cut-off date') as HTMLInputElement
    await waitFor(() => expect(cutoff.value).toBe('2026-06-01'))

    fireEvent.change(cutoff, { target: { value: '2026-07-15' } }) // operator edit
    expect(screen.getByText(/Cut-off basis:/)).toHaveTextContent('Operator supplied')

    fireEvent.click(screen.getByRole('button', { name: 'Generate DB-backed forecast' }))
    await waitFor(() =>
      expect(startDbConfigMock).toHaveBeenCalledWith({
        project_key: 'tropical',
        generator_kind: 'comprehensive',
        forecast_start_date: '2025-01-01',
        forecast_cutoff_date: '2026-07-15',
        forecast_cutoff_date_basis: 'operator_supplied',
      }),
    )
  })

  // UI-A: context header.
  it('renders the forecast context header with a no-selection state', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Forecast context')).toBeInTheDocument()
    expect(screen.getByText('No project selected')).toBeInTheDocument()
    expect(screen.getByText('No output selected')).toBeInTheDocument()
    // The single next-step line guides the operator before any selection.
    expect(screen.getByText('Select a project to view its forecast.')).toBeInTheDocument()
  })

  it('hides forecast result panels until a project is explicitly selected', () => {
    mockData()
    renderPage()
    // No project selected → labelled empty state, no implicit projects[0] browsing.
    expect(screen.getByText('Select a project to view its forecast results.')).toBeInTheDocument()
    expect(screen.queryByText('Persisted forecast outputs')).not.toBeInTheDocument()
    expect(screen.queryByText('Forecast explainability')).not.toBeInTheDocument()
    expect(screen.queryByText('Operator assumptions')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    expect(screen.getByText('Persisted forecast outputs')).toBeInTheDocument()
    expect(screen.getByText('Forecast explainability')).toBeInTheDocument()
    expect(screen.getByText('Operator assumptions')).toBeInTheDocument()
  })

  it('renders the results summary and forecast health above the detail tables', () => {
    mockData()
    renderPage()
    // Summaries are gated on selection, like the detail panels.
    expect(screen.queryByText('Results summary')).not.toBeInTheDocument()
    expect(screen.queryByText('Forecast health')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    expect(screen.getByText('Results summary')).toBeInTheDocument()
    expect(screen.getByText('Forecast health')).toBeInTheDocument()
    // Default mock has no persisted outputs → an explicit, readable verdict (not raw data).
    expect(screen.getByText('Blocked / no output')).toBeInTheDocument()
    expect(screen.getByText('No forecast output yet')).toBeInTheDocument()
  })

  it('updates the header and enables generation only for a ready project', () => {
    mockData()
    renderPage()
    const dbGenerate = () => screen.getByRole('button', { name: 'Generate DB-backed forecast' })

    // Blocked project: header surfaces the reason + a resolve-first next step; generation disabled.
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'harbor' } })
    expect(
      screen.getByText('No budget, cost, or baseline data is available to forecast from yet.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Resolve readiness items before generating.')).toBeInTheDocument()
    expect(dbGenerate()).toBeDisabled()

    // Ready project: header shows the latest forecast + review-or-generate next step; control enables.
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    expect(screen.getByText('Jun 19, 2026')).toBeInTheDocument()
    expect(screen.getByText('Review the latest forecast or generate a new one.')).toBeInTheDocument()
    expect(dbGenerate()).not.toBeDisabled()
  })

  it('shows a failed selected run without implying a persisted output exists', () => {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      const kind = opts.queryKey[1]
      const sub = opts.queryKey[2]
      if (kind === 'run-detail') {
        return {
          data: {
            display_label: 'Context → analysis forecast — Jun 20, 2026 1:07 PM',
            status: 'failed',
            message: 'Generation did not complete.',
            no_live_writes: true,
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'runs' && sub === 'db-config') {
        return { data: { runs: [] }, isLoading: false, error: null, refetch: vi.fn() }
      }
      if (kind === 'runs') {
        return {
          data: {
            runs: [
              {
                run_id: 'abc123',
                display_label: 'Context → analysis forecast — Jun 20, 2026 1:07 PM',
                status: 'failed',
                generated_display: 'Jun 20, 2026 1:07 PM',
              },
            ],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'readiness') {
        return {
          data: { ready: true, generation_enabled: true, disabled_reasons: [], warnings: [], actions: [], guardrails: {} },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'projects') {
        return {
          data: { projects: [] },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
    })
    renderPage()
    fireEvent.click(screen.getAllByRole('button', { name: 'Open' })[0])

    // The header states plainly that no output was produced, and shows no viewed output.
    expect(
      screen.getByText('The selected run did not complete; no forecast output was produced.'),
    ).toBeInTheDocument()
    expect(screen.getByText('No output selected')).toBeInTheDocument()
    // The failed status is visible (header selected-run line + run-detail panel).
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0)
    // UI-B: the failed run is visually separated from output — its detail shows a no-output
    // statement and does NOT offer the "review output" affordance that implies a usable forecast.
    expect(screen.getByText('Run did not complete')).toBeInTheDocument()
    expect(
      screen.getByText('No forecast output was produced for this run.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Review packages on overview')).not.toBeInTheDocument()
  })

  // UI-B: generation workflow.
  it('shows exactly one primary Generate CTA and hides the legacy path by default', () => {
    mockData()
    renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    expect(
      screen.getAllByRole('button', { name: /Generate DB-backed forecast/i }),
    ).toHaveLength(1)
    // The legacy file-config generation is not a primary visible action.
    expect(
      screen.queryByRole('button', { name: /Generate file-config forecast/i }),
    ).not.toBeInTheDocument()
  })

  it('labels a failed generation request "Failed" (not "Unreadable") with safe coded copy', () => {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      const kind = opts.queryKey[1]
      const sub = opts.queryKey[2]
      if (kind === 'generation' && sub === 'requests') {
        return {
          data: {
            surface: 'analytics.forecast_generation_requests',
            requests: [
              {
                request_id: 'req-1',
                run_id: null,
                project_key: 'tropical',
                generation_mode: 'db_config',
                generator_kind: 'comprehensive',
                request_status: 'failed',
                validation_status: 'valid',
                forecast_start_date: null,
                forecast_cutoff_date: null,
                forecast_cutoff_date_basis: null,
                readiness_status_at_request: 'ready',
                readiness_reasons: [],
                failure_code: 'source_package_missing',
                // null message forces the coded-copy fallback (the riskier path): the raw code
                // must be translated to safe copy and never rendered verbatim.
                failure_message: null,
                created_utc: '2026-06-25T10:00:00+00:00',
                updated_utc: '2026-06-25T10:00:00+00:00',
              },
            ],
            guardrails: { read_only: true },
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'readiness') {
        return {
          data: { ready: true, generation_enabled: true, disabled_reasons: [], warnings: [], actions: [], guardrails: {} },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'projects') {
        return {
          data: {
            projects: [
              { project_key: 'tropical', display_name: 'Tropical', readiness_status: 'ready', readiness_reasons: [] },
            ],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'date-defaults') {
        return {
          data: {
            project_key: 'tropical',
            forecast_start_date: null,
            forecast_cutoff_date: null,
            forecast_cutoff_date_basis: null,
            schedule_version_key: null,
            schedule_data_date: null,
            warnings: [],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: { runs: [] }, isLoading: false, error: null, refetch: vi.fn() }
    })
    const { container } = renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })

    // Scope to the request row: other surfaces (e.g. the no-output health pill) legitimately
    // still use "Unreadable" — only failed/rejected generation requests must not.
    const requestsSection = screen.getByText('Recent generation requests').closest('section')!
    const requests = within(requestsSection)
    // Accurate outcome label — never the misleading "Unreadable" for a failed request.
    expect(requests.getByText('Failed')).toBeInTheDocument()
    expect(requests.queryByText('Unreadable')).not.toBeInTheDocument()
    // The failure_code is surfaced as safe, path-free copy (mapped, not the raw code).
    expect(requests.getByText("Forecast source data isn't available yet.")).toBeInTheDocument()

    // No raw code, source-package path, or filesystem path leaks to the operator.
    const text = container.textContent || ''
    expect(text).not.toMatch(/source_package_missing/)
    expect(text).not.toMatch(/cost_forecast_json_package/)
    expect(text).not.toMatch(/\/Users\//)
  })

  it('renders safe copy for db_native_generation_not_implemented and keeps readiness maturity-driven', () => {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      const kind = opts.queryKey[1]
      const sub = opts.queryKey[2]
      if (kind === 'generation' && sub === 'requests') {
        return {
          data: {
            surface: 'analytics.forecast_generation_requests',
            requests: [
              {
                request_id: 'req-dbn',
                run_id: null,
                project_key: 'summit',
                generation_mode: 'db_config',
                generator_kind: 'comprehensive',
                request_status: 'failed',
                validation_status: 'valid',
                forecast_start_date: null,
                forecast_cutoff_date: null,
                forecast_cutoff_date_basis: null,
                readiness_status_at_request: 'degraded',
                readiness_reasons: ['missing_config_snapshot'],
                failure_code: 'db_native_generation_not_implemented',
                failure_message: null, // force the coded-copy fallback; raw code must never render
                created_utc: '2026-06-25T10:00:00+00:00',
                updated_utc: '2026-06-25T10:00:00+00:00',
              },
            ],
            guardrails: { read_only: true },
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'readiness') {
        return {
          data: { ready: true, generation_enabled: true, disabled_reasons: [], warnings: [], actions: [], guardrails: {} },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'projects') {
        return {
          data: {
            // A sparse, degraded (but calculable) project — readiness stays maturity-driven.
            projects: [
              {
                project_key: 'summit',
                display_name: 'Summit Center',
                readiness_status: 'degraded',
                readiness_reasons: ['missing_config_snapshot'],
                forecast_maturity: 'baseline_only',
                confidence_level: 'low',
              },
            ],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'date-defaults') {
        return {
          data: {
            project_key: 'summit',
            forecast_start_date: null,
            forecast_cutoff_date: null,
            forecast_cutoff_date_basis: null,
            schedule_version_key: null,
            schedule_data_date: null,
            warnings: [],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: { runs: [] }, isLoading: false, error: null, refetch: vi.fn() }
    })
    const { container } = renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'summit' } })

    const requestsSection = screen.getByText('Recent generation requests').closest('section')!
    const requests = within(requestsSection)
    // Honest runtime-capability failure: "Failed", never "Unreadable".
    expect(requests.getByText('Failed')).toBeInTheDocument()
    expect(requests.queryByText('Unreadable')).not.toBeInTheDocument()
    // Safe, path-free copy mapped from the code (conveys readiness is still valid).
    expect(requests.getByText(/DB-native (forecast )?generation isn't available yet/i)).toBeInTheDocument()

    // Readiness stays driven by project maturity, NOT the runtime failure code: a degraded (calculable)
    // project is still selectable and generatable.
    expect(
      screen.getByRole('button', { name: 'Generate DB-backed forecast' }),
    ).not.toBeDisabled()

    // No raw code, package name, or filesystem path leaks.
    const text = container.textContent || ''
    expect(text).not.toMatch(/db_native_generation_not_implemented/)
    expect(text).not.toMatch(/cost_forecast_json_package/)
    expect(text).not.toMatch(/\/Users\//)
  })

  it('treats a db-config POST that returns request_status="failed" as an honest failed request, not a successful submission', async () => {
    // Backend fails closed with HTTP 200 + request_status="failed" (db_native not implemented).
    // The POST handler must surface curated copy and suppress the success banner.
    startDbConfigMock.mockResolvedValueOnce({
      request_id: 'req-x',
      request_status: 'failed',
      failure_code: 'db_native_generation_not_implemented',
      failure_message: null, // force the coded-copy fallback; raw code must never render
    })
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      const kind = opts.queryKey[1]
      const sub = opts.queryKey[2]
      if (kind === 'generation' && sub === 'requests') {
        // Empty request log so the ONLY source of failure copy is the POST handler itself.
        return {
          data: { surface: 'analytics.forecast_generation_requests', requests: [] },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'readiness') {
        return {
          data: { ready: true, generation_enabled: true, disabled_reasons: [], warnings: [], actions: [], guardrails: {} },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'projects') {
        return {
          data: {
            projects: [
              { project_key: 'tropical', display_name: 'Tropical', readiness_status: 'ready', readiness_reasons: [] },
            ],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      if (kind === 'generation' && sub === 'date-defaults') {
        return {
          data: {
            project_key: 'tropical',
            forecast_start_date: null,
            forecast_cutoff_date: null,
            forecast_cutoff_date_basis: null,
            schedule_version_key: null,
            schedule_data_date: null,
            warnings: [],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: { runs: [] }, isLoading: false, error: null, refetch: vi.fn() }
    })
    const { container } = renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate DB-backed forecast' }))

    // Honest unsupported/failed state: curated, path-free copy is shown in the Generate panel.
    const generatePanel = (await screen.findByText('Generate forecast')).closest('section')!
    const generate = within(generatePanel)
    expect(
      generate.getByText(/DB-native (forecast )?generation isn't available yet/i),
    ).toBeInTheDocument()
    // The optimistic success banner must NOT render for a failed request.
    expect(screen.queryByText(/Generation request submitted/i)).not.toBeInTheDocument()
    // A failed generation request is never labelled "Unreadable" (other surfaces — e.g. the
    // no-output health pill — legitimately still use it, so scope to the Generate panel).
    expect(generate.queryByText('Unreadable')).not.toBeInTheDocument()
    // No raw code, source package name, or filesystem path leaks to the operator.
    const text = container.textContent || ''
    expect(text).not.toMatch(/db_native_generation_not_implemented/)
    expect(text).not.toMatch(/cost_forecast_json_package/)
    expect(text).not.toMatch(/\/Users\//)
  })

  it('still shows the success banner when a db-config POST returns a completed request', async () => {
    mockData()
    startDbConfigMock.mockResolvedValueOnce({ request_id: 'req-ok', request_status: 'completed' })
    renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate DB-backed forecast' }))
    expect(await screen.findByText(/Generation request submitted/i)).toBeInTheDocument()
  })

  it('reveals the legacy file-config generation only behind the advanced disclosure', () => {
    mockData()
    renderPage()
    fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: 'tropical' } })
    expect(
      screen.queryByRole('button', { name: /Generate file-config forecast/i }),
    ).not.toBeInTheDocument()

    fireEvent.click(
      screen.getByRole('button', { name: /Advanced \/ legacy file-configuration generation/i }),
    )
    expect(
      screen.getByRole('button', { name: /Generate file-config forecast/i }),
    ).toBeInTheDocument()
  })
})
