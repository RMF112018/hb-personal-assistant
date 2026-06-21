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
    proposeForecastConfigEdit: vi.fn(),
  },
}))

function mockQueries(edits: unknown[] = []) {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
    const kind = opts.queryKey[2]
    if (kind === 'snapshots') {
      return { data: { snapshots: [{ snapshot_id: 'snap1' }] }, refetch: vi.fn() }
    }
    return { data: { edits }, refetch: vi.fn() }
  })
}

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
    mockQueries([{ edit_id: 'e123', created_display: 'Jun 21, 2026', parity_status: 'pass', changed_count: 2 }])
    renderPage()
    expect(screen.getByText('Proposals')).toBeInTheDocument()
    expect(screen.getByText('e123')).toBeInTheDocument()
  })
})
