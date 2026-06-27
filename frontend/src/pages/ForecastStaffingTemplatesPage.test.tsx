import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastStaffingTemplatesPage } from './ForecastStaffingTemplatesPage'

const useQueryMock = vi.fn()
const getRoleMock = vi.fn(() => 'operator')

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

vi.mock('../lib/api', () => ({
  getLocalUiRole: () => getRoleMock(),
  api: {
    getForecastStaffingTemplates: vi.fn(),
    createForecastStaffingTemplate: vi.fn(),
    getForecastStaffingTemplate: vi.fn(),
    addForecastStaffingTemplateVersion: vi.fn(),
    deleteForecastStaffingTemplate: vi.fn(),
  },
}))

import { api } from '../lib/api'

const TEMPLATES = [
  { template_id: 't1', template_key: 'super-fl', template_name: 'FL Super', active_status: 'active' },
]
const VERSIONS = [
  { template_version_id: 'v1', version_number: 1, cost_code: '01-100', default_role_title: 'Super', default_lab_rate: '2500' },
]

function mockQueries() {
  useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
    if (opts.queryKey[1] === 'staffing-templates') return { data: { templates: TEMPLATES }, refetch: vi.fn() }
    if (opts.queryKey[1] === 'staffing-template') return { data: { versions: VERSIONS }, refetch: vi.fn() }
    return { data: undefined, refetch: vi.fn() }
  })
}

function renderPage() {
  return render(<MemoryRouter><ForecastStaffingTemplatesPage /></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  getRoleMock.mockReturnValue('operator')
  mockQueries()
})

describe('Forecast staffing templates admin', () => {
  it('lists templates', () => {
    renderPage()
    expect(screen.getByText('super-fl')).toBeInTheDocument()
    expect(screen.getByText('FL Super')).toBeInTheDocument()
  })

  it('creates a template as operator', async () => {
    vi.mocked(api.createForecastStaffingTemplate).mockResolvedValue({ ok: true } as never)
    renderPage()
    fireEvent.change(screen.getByLabelText('Template key'), { target: { value: 'pm-fl' } })
    fireEvent.change(screen.getByLabelText('Template name'), { target: { value: 'FL PM' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create template' }))
    await waitFor(() =>
      expect(api.createForecastStaffingTemplate).toHaveBeenCalledWith({
        template_key: 'pm-fl', template_name: 'FL PM',
      }),
    )
  })

  it('shows versions and adds one with a cost code', async () => {
    vi.mocked(api.addForecastStaffingTemplateVersion).mockResolvedValue({ ok: true } as never)
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Versions' }))
    expect(await screen.findByText('01-100')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Cost code'), { target: { value: '02-200' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add version' }))
    await waitFor(() =>
      expect(api.addForecastStaffingTemplateVersion).toHaveBeenCalledWith(
        't1', expect.objectContaining({ cost_code: '02-200' }),
      ),
    )
  })

  it('surfaces an ok:false add-version error', async () => {
    vi.mocked(api.addForecastStaffingTemplateVersion).mockResolvedValue({
      ok: false, errors: [{ message: 'Template version requires a cost code.' }],
    } as never)
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Versions' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Add version' }))
    expect(await screen.findByText('Template version requires a cost code.')).toBeInTheDocument()
  })

  it('deactivates a template', async () => {
    vi.mocked(api.deleteForecastStaffingTemplate).mockResolvedValue({ ok: true } as never)
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }))
    await waitFor(() => expect(api.deleteForecastStaffingTemplate).toHaveBeenCalledWith('t1'))
  })

  it('hides write controls for viewers', () => {
    getRoleMock.mockReturnValue('viewer')
    renderPage()
    expect(screen.queryByRole('button', { name: 'Create template' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Versions' })).toBeInTheDocument()
  })
})
