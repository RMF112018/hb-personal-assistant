import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

  it('renders the generate action and run history', () => {
    mockData()
    renderPage()
    expect(screen.getAllByText('Generate forecast').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: /Generate forecast/i }).length).toBeGreaterThan(0)
    expect(screen.getByText('Generation history')).toBeInTheDocument()
    expect(
      screen.getByText('Context → analysis forecast — Jun 20, 2026 1:07 PM'),
    ).toBeInTheDocument()
  })

  it('renders the live-config generation action and merges both run sources', () => {
    mockData()
    renderPage()
    expect(
      screen.getByRole('button', { name: /^Generate$/i }),
    ).toBeInTheDocument()
    // both a file-config and a live-config run appear, with a Source column distinguishing them
    expect(
      screen.getByText('Comprehensive forecast from live config — Jun 21, 2026 9:00 AM'),
    ).toBeInTheDocument()
    expect(screen.getByText('Live configuration')).toBeInTheDocument()
    expect(screen.getByText('File configuration')).toBeInTheDocument()
  })

  it('offers all four generator kinds and passes the selected kind to the API', async () => {
    mockData()
    renderPage()
    const select = screen.getByLabelText('Forecast type') as HTMLSelectElement
    const optionValues = Array.from(select.options).map((o) => o.value)
    expect(optionValues).toEqual(['comprehensive', 'model_controls', 'monthly', 'probability'])

    fireEvent.change(select, { target: { value: 'monthly' } })
    fireEvent.click(screen.getByRole('button', { name: /^Generate$/i }))
    await waitFor(() => expect(startDbConfigMock).toHaveBeenCalledWith('monthly'))
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

    const button = screen.getByRole('button', { name: /^Generate$/i })
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

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d{8}_\d{6}/)
    expect(text).not.toMatch(/\/Users\//)
  })

  it('renders a multi-project selector when more than one project has outputs', () => {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      if (opts.queryKey[1] === 'db-projects') {
        return {
          data: {
            projects: [
              { project_key: 'tropical', output_count: 2, latest_display: 'Jun 19, 2026' },
              { project_key: 'harbor', output_count: 1, latest_display: 'Jun 18, 2026' },
            ],
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
    })
    renderPage()
    const select = screen.getByLabelText('Forecast project') as HTMLSelectElement
    expect(Array.from(select.options).map((o) => o.value)).toEqual(['tropical', 'harbor'])
  })

  it('hides the project selector when only one project has outputs', () => {
    useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
      if (opts.queryKey[1] === 'db-projects') {
        return {
          data: { projects: [{ project_key: 'tropical', output_count: 2, latest_display: null }] },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
    })
    renderPage()
    expect(screen.queryByLabelText('Forecast project')).toBeNull()
  })
})
