import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectForecastOutputSelector } from './ProjectForecastOutputSelector'
import { selectForecastOutput } from './projectForecastOutputSelection'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown }) => useQueryMock(options),
}))

const OUTPUTS = [
  {
    output_id: 'out-002',
    project_key: 'harbor',
    estimated_final_cost: '61366869',
    cost_to_complete: null,
    variance_to_budget: null,
    variance_to_prior_forecast: null,
    created_display: 'Jun 26, 2026',
  },
  {
    output_id: 'out-001',
    project_key: 'harbor',
    estimated_final_cost: '60000000',
    cost_to_complete: null,
    variance_to_budget: null,
    variance_to_prior_forecast: null,
    created_display: 'May 10, 2026',
  },
]

type State = { isLoading: boolean; error: unknown; outputs: typeof OUTPUTS }
let state: State

function setState(overrides: Partial<State>) {
  state = { isLoading: false, error: null, outputs: OUTPUTS, ...overrides }
}

function mockQuery() {
  useQueryMock.mockImplementation(() => ({
    data: state.error ? undefined : { outputs: state.outputs },
    isLoading: state.isLoading,
    error: state.error,
    refetch: vi.fn(),
  }))
}

describe('selectForecastOutput', () => {
  it('uses a valid requested output id', () => {
    expect(selectForecastOutput(OUTPUTS, 'out-001')).toEqual({
      selectedOutputId: 'out-001',
      isInvalidSelection: false,
    })
  })

  it('falls back to the latest output when none is requested', () => {
    expect(selectForecastOutput(OUTPUTS, null)).toEqual({
      selectedOutputId: 'out-002',
      isInvalidSelection: false,
    })
    expect(selectForecastOutput(OUTPUTS, undefined)).toEqual({
      selectedOutputId: 'out-002',
      isInvalidSelection: false,
    })
  })

  it('flags an invalid/foreign requested id and falls back to latest', () => {
    expect(selectForecastOutput(OUTPUTS, 'out-999')).toEqual({
      selectedOutputId: 'out-002',
      isInvalidSelection: true,
    })
  })

  it('returns no selection (and never flags invalid) while outputs are empty', () => {
    expect(selectForecastOutput([], 'out-999')).toEqual({
      selectedOutputId: null,
      isInvalidSelection: false,
    })
  })
})

describe('ProjectForecastOutputSelector', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    setState({})
    mockQuery()
  })

  it('renders the forecast history list with business-facing labels', () => {
    render(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={vi.fn()} />,
    )

    expect(screen.getByRole('heading', { name: 'Forecast History' })).toBeInTheDocument()
    expect(screen.getByText('Jun 26, 2026')).toBeInTheDocument()
    expect(screen.getByText('May 10, 2026')).toBeInTheDocument()
    expect(screen.getByText('Latest')).toBeInTheDocument()
    // Raw output ids are never the visible label.
    expect(screen.queryByText('out-002')).not.toBeInTheDocument()
    expect(screen.queryByText('out-001')).not.toBeInTheDocument()
  })

  it('marks the resolved selected output and defaults to latest', () => {
    render(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: /Jun 26, 2026/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('button', { name: /May 10, 2026/ })).not.toHaveAttribute('aria-current')
  })

  it('marks the requested output when valid', () => {
    render(
      <ProjectForecastOutputSelector
        projectKey="harbor"
        requestedOutputId="out-001"
        onSelectOutput={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /May 10, 2026/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('calls onSelectOutput with the chosen output id', () => {
    const onSelect = vi.fn()
    render(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={onSelect} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /May 10, 2026/ }))
    expect(onSelect).toHaveBeenCalledWith('out-001')
  })

  it('warns and falls back to latest for an invalid requested output', () => {
    render(
      <ProjectForecastOutputSelector
        projectKey="harbor"
        requestedOutputId="out-999"
        onSelectOutput={vi.fn()}
      />,
    )
    expect(
      screen.getByText(
        'The selected forecast output is not available for this project. Showing the latest available output.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Jun 26, 2026/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('renders loading, error, and empty states', () => {
    setState({ isLoading: true })
    const { rerender } = render(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={vi.fn()} />,
    )
    expect(screen.getByText('Loading forecast history…')).toBeInTheDocument()

    setState({ error: new Error('boom') })
    rerender(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={vi.fn()} />,
    )
    expect(
      screen.getByText(
        'Forecast history could not be loaded. Check the local data connection and try again.',
      ),
    ).toBeInTheDocument()

    setState({ outputs: [] })
    rerender(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={vi.fn()} />,
    )
    expect(
      screen.getByText('No forecast outputs are available for this project yet.'),
    ).toBeInTheDocument()
  })

  it('scopes the outputs read to the route project key', () => {
    render(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId={null} onSelectOutput={vi.fn()} />,
    )
    expect(useQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['forecast', 'db-outputs', 'harbor'] }),
    )
  })

  it('omits forbidden implementation copy', () => {
    render(
      <ProjectForecastOutputSelector projectKey="harbor" requestedOutputId="out-999" onSelectOutput={vi.fn()} />,
    )
    const text = document.body.textContent || ''
    for (const forbidden of [
      'read model',
      'procore_ep_projects',
      'projection',
      'raw payload',
      'JSON',
      'source package',
      '/Users/',
      'stack trace',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })
})
