import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastConfigEditProposalsPage } from './ForecastConfigEditProposalsPage'

const useQueryMock = vi.fn()
const getRoleMock = vi.fn(() => 'operator')

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

vi.mock('../lib/api', () => ({
  getLocalUiRole: () => getRoleMock(),
  api: {
    getForecastConfigSnapshots: vi.fn(),
    getForecastConfigEdits: vi.fn(),
    getForecastRuntimeStatus: vi.fn(),
    proposeForecastConfigEdit: vi.fn(),
    promoteForecastConfigEdit: vi.fn(),
  },
}))

function mockQueries(edits: unknown[] = [], promotionEnabled = false) {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
    if (opts.queryKey[1] === 'runtime') {
      return { data: { promotion: { enabled: promotionEnabled } }, refetch: vi.fn() }
    }
    if (opts.queryKey[2] === 'snapshots') {
      return { data: { snapshots: [{ snapshot_id: 'snap1' }] }, refetch: vi.fn() }
    }
    return { data: { edits }, refetch: vi.fn() }
  })
}

const PASS_EDIT = { edit_id: 'e123', created_display: 'Jun 21, 2026', parity_status: 'pass', status: 'succeeded', changed_count: 2 }

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastConfigEditProposalsPage />
    </MemoryRouter>,
  )
}

describe('ForecastConfigEditProposalsPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    getRoleMock.mockReturnValue('operator')
  })

  it('renders the propose form for an operator with editable domains', () => {
    mockQueries()
    renderPage()
    expect(screen.getByText('Propose a configuration edit')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Propose edit/i })).toBeInTheDocument()
    expect(screen.getByText('Model controls')).toBeInTheDocument()
  })

  it('hides the propose form for a viewer', () => {
    getRoleMock.mockReturnValue('viewer')
    mockQueries()
    renderPage()
    expect(screen.queryByText('Propose a configuration edit')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Propose edit/i })).not.toBeInTheDocument()
  })

  it('lists prior proposals', () => {
    mockQueries([PASS_EDIT])
    renderPage()
    expect(screen.getByText('Proposals')).toBeInTheDocument()
    expect(screen.getByText('e123')).toBeInTheDocument()
  })

  it('shows the Promote action only when promotion is enabled', () => {
    mockQueries([PASS_EDIT], true)
    renderPage()
    expect(screen.getByRole('button', { name: /Promote to live/i })).toBeInTheDocument()
  })

  it('hides the Promote action when promotion is disabled', () => {
    mockQueries([PASS_EDIT], false)
    renderPage()
    expect(screen.queryByRole('button', { name: /Promote to live/i })).not.toBeInTheDocument()
    expect(screen.getByText(/Live promotion is turned off/i)).toBeInTheDocument()
  })

  it('hides the Promote action for a viewer even when enabled', () => {
    getRoleMock.mockReturnValue('viewer')
    mockQueries([PASS_EDIT], true)
    renderPage()
    expect(screen.queryByRole('button', { name: /Promote to live/i })).not.toBeInTheDocument()
  })
})
