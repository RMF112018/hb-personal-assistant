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

  it('shows readiness checklist and storage settings CTA when not fully ready', () => {
    useReadinessMock.mockReturnValue({
      isLoading: false,
      data: {
        storage_mode: 'app_managed',
        roots: {
          package_roots: { valid: true, blocker: null, count: 1 },
          data_root: { valid: false, blocker: 'not_configured' },
          db_path: { valid: true, blocker: null, schema_version: 61, config_snapshot_count: 2 },
          runs_root: { valid: true },
          eval_root: { valid: false, blocker: 'not_configured' },
          config_edit_root: { valid: true },
        },
      },
    })
    renderPanel()

    expect(screen.getByText('Forecast readiness')).toBeInTheDocument()
    expect(screen.getByText(/1 package folder ready/)).toBeInTheDocument()
    expect(screen.getByText(/Database ready/)).toBeInTheDocument()
    expect(screen.getByText(/Not ready — Generate forecasts/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open storage settings/i })).toHaveAttribute(
      'href',
      '/forecasting/runtime',
    )
  })

  it('renders nothing when all storage areas are ready', () => {
    useReadinessMock.mockReturnValue({
      isLoading: false,
      data: {
        storage_mode: 'app_managed',
        roots: {
          package_roots: { valid: true, count: 3 },
          data_root: { valid: true },
          db_path: { valid: true, schema_version: 61, config_snapshot_count: 1 },
          runs_root: { valid: true },
          eval_root: { valid: true },
          config_edit_root: { valid: true },
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
      data: {
        storage_mode: 'app_managed',
        roots: {
          package_roots: { valid: false, blocker: 'not_configured' },
          data_root: { valid: false },
          db_path: { valid: false },
          runs_root: { valid: false },
          eval_root: { valid: false },
          config_edit_root: { valid: false },
        },
      },
    })
    renderPanel()
    expect(screen.getByRole('link', { name: /View storage settings/i })).toBeInTheDocument()
  })
})