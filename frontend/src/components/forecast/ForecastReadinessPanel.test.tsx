import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastReadinessPanel } from './ForecastReadinessPanel'

const useReadinessMock = vi.fn()
const getRoleMock = vi.fn(() => 'operator')

vi.mock('../../hooks/useForecastReadiness', () => ({
  useForecastReadiness: () => useReadinessMock(),
}))

vi.mock('../../lib/api', () => ({
  getLocalUiRole: () => getRoleMock(),
}))

function renderPanel() {
  return render(
    <MemoryRouter>
      <ForecastReadinessPanel />
    </MemoryRouter>,
  )
}

describe('ForecastReadinessPanel', () => {
  beforeEach(() => {
    useReadinessMock.mockReset()
    getRoleMock.mockReturnValue('operator')
  })

  it('shows the checklist with advisory counts and a configure CTA when read-roots are missing', () => {
    useReadinessMock.mockReturnValue({
      isLoading: false,
      data: {
        roots: {
          package_roots: { valid: true, blocker: null, count: 1 },
          data_root: { valid: false, blocker: 'not_configured' },
          db_path: { valid: true, blocker: null, schema_version: 61, config_snapshot_count: 2 },
        },
      },
    })
    renderPanel()

    expect(screen.getByText('Set up forecast data sources')).toBeInTheDocument()
    // redaction-safe advisory counts, not paths
    expect(screen.getByText(/1 forecast package found/)).toBeInTheDocument()
    expect(screen.getByText(/schema v61, 2 config snapshots/)).toBeInTheDocument()
    // a not-configured read-root surfaces friendly blocker copy + what it unlocks
    expect(screen.getByText(/Not configured — Unlocks running forecasts/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Configure data sources/i })).toHaveAttribute(
      'href',
      '/forecasting/runtime',
    )
  })

  it('renders nothing when all read-roots are ready', () => {
    useReadinessMock.mockReturnValue({
      isLoading: false,
      data: {
        roots: {
          package_roots: { valid: true, count: 3 },
          data_root: { valid: true },
          db_path: { valid: true, schema_version: 61, config_snapshot_count: 1 },
        },
      },
    })
    const { container } = renderPanel()
    expect(container).toBeEmptyDOMElement()
  })

  it('uses view-only CTA copy for a viewer role', () => {
    getRoleMock.mockReturnValue('viewer')
    useReadinessMock.mockReturnValue({
      isLoading: false,
      data: { roots: { package_roots: { valid: false, blocker: 'not_configured' }, data_root: { valid: false }, db_path: { valid: false } } },
    })
    renderPanel()
    expect(screen.getByRole('link', { name: /View data source setup/i })).toBeInTheDocument()
  })
})
