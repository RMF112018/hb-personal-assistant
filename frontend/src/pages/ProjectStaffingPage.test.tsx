import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { StaffingReadinessSummary } from '../components/staffing/StaffingReadinessSummary'
import { StaffingConfigGrid } from '../components/staffing/StaffingConfigGrid'
import { StaffingAssumptionsPanel } from '../components/staffing/StaffingAssumptionsPanel'
import { StaffingAttributionReview } from '../components/staffing/StaffingAttributionReview'
import { StaffingMatSummary } from '../components/staffing/StaffingMatSummary'

vi.mock('../lib/api', () => ({
  getLocalUiRole: vi.fn(() => 'operator'),
  api: {
    getProjectStaffingConfig: vi.fn(),
    createProjectStaffingConfig: vi.fn(),
    updateProjectStaffingConfig: vi.fn(),
    deleteProjectStaffingConfig: vi.fn(),
    getProjectStaffingAssumptions: vi.fn(),
    updateProjectStaffingAssumptions: vi.fn(),
    getProjectStaffingReadiness: vi.fn(),
    getProjectStaffingUnmatched: vi.fn(),
    resolveProjectStaffingReview: vi.fn(),
    getProjectStaffingMatSummary: vi.fn(),
    getForecastHolidayCalendars: vi.fn(),
  },
}))

import { api, getLocalUiRole } from '../lib/api'

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getLocalUiRole).mockReturnValue('operator')
})

describe('Project staffing UI', () => {
  it('shows a blocked readiness pill with humanized reasons', async () => {
    vi.mocked(api.getProjectStaffingReadiness).mockResolvedValue({
      readiness_status: 'blocked',
      readiness_reasons: ['employment_type_invalid'],
      active_row_count: 1,
      unmatched_review_count: 0,
    } as never)
    renderWithClient(<StaffingReadinessSummary project="tropical" />)
    expect(await screen.findByText('Not ready')).toBeInTheDocument()
    expect(screen.getByText('Employment type invalid')).toBeInTheDocument()
  })

  it('creates a staffing row as operator', async () => {
    vi.mocked(api.getProjectStaffingConfig).mockResolvedValue({ rows: [] } as never)
    vi.mocked(api.createProjectStaffingConfig).mockResolvedValue({ ok: true } as never)
    renderWithClient(<StaffingConfigGrid project="tropical" />)
    fireEvent.change(await screen.findByLabelText('Role/title'), { target: { value: 'Super' } })
    fireEvent.change(screen.getByLabelText('Cost code'), { target: { value: '01-100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add row' }))
    await waitFor(() =>
      expect(api.createProjectStaffingConfig).toHaveBeenCalledWith(
        'tropical',
        expect.objectContaining({ role_title: 'Super', cost_code: '01-100' }),
      ),
    )
  })

  it('keeps an invalid row visible with its field errors', async () => {
    vi.mocked(api.getProjectStaffingConfig).mockResolvedValue({
      rows: [{
        staffing_config_id: 'c1', project_key: 'tropical', template_id: null, role_title: '',
        person_name: null, employment_type: 'Full Time', cost_code: '01-100',
        cost_code_description: null, rate_unit: 'weekly', lab_rate: '1', lbn_rate: null,
        mat_rate: null, start_date: '2026-07-01', finish_date: '2026-12-31',
        active_status: 'active', override_fields_json: [], validation_status: 'invalid',
        validation_errors_json: [{ field: 'role_title', code: 'role_title_missing', message: 'Role/title is required.' }],
        updated_utc: 't',
      }],
    } as never)
    renderWithClient(<StaffingConfigGrid project="tropical" />)
    expect(await screen.findByText('Role/title is required.')).toBeInTheDocument()
    expect(screen.getByText(/Needs attention/)).toBeInTheDocument()
  })

  it('hides write controls for viewers', async () => {
    vi.mocked(getLocalUiRole).mockReturnValue('viewer')
    vi.mocked(api.getProjectStaffingConfig).mockResolvedValue({ rows: [] } as never)
    renderWithClient(<StaffingConfigGrid project="tropical" />)
    await screen.findByText('No staffing rows yet.')
    expect(screen.queryByRole('button', { name: 'Add row' })).not.toBeInTheDocument()
  })

  it('surfaces a bad holiday-calendar assumption error', async () => {
    vi.mocked(api.getProjectStaffingAssumptions).mockResolvedValue({
      assumptions: { hours_per_business_day: '8.00', business_days_per_week: '5.00',
        full_time_hours_per_week: '40.00', holiday_calendar_id: null },
    } as never)
    vi.mocked(api.getForecastHolidayCalendars).mockResolvedValue({ calendars: [] } as never)
    vi.mocked(api.updateProjectStaffingAssumptions).mockResolvedValue({
      ok: false, errors: [{ message: 'Unknown holiday calendar.' }],
    } as never)
    renderWithClient(<StaffingAssumptionsPanel project="tropical" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Save assumptions' }))
    expect(await screen.findByText('Unknown holiday calendar.')).toBeInTheDocument()
  })

  it('resolves an attribution review item to a staffing row', async () => {
    vi.mocked(api.getProjectStaffingUnmatched).mockResolvedValue({
      review_items: [{ review_item_id: 'r1', cost_code: '01-100', category: 'LAB',
        actual_amount: '1500.00', actuals_start_month: '2026-06', actuals_through_month: '2026-07',
        description_label: 'Labor' }],
    } as never)
    vi.mocked(api.getProjectStaffingConfig).mockResolvedValue({
      rows: [{ staffing_config_id: 'c1', role_title: 'Super', person_name: 'Jane', cost_code: '01-100' }],
    } as never)
    vi.mocked(api.resolveProjectStaffingReview).mockResolvedValue({ ok: true } as never)
    renderWithClient(<StaffingAttributionReview project="tropical" />)
    fireEvent.change(await screen.findByLabelText('Staffing row'), { target: { value: 'c1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Attribute' }))
    await waitFor(() =>
      expect(api.resolveProjectStaffingReview).toHaveBeenCalledWith(
        'tropical', 'r1', { staffing_config_id: 'c1' },
      ),
    )
  })

  it('renders the MAT summary read-only', async () => {
    vi.mocked(api.getProjectStaffingMatSummary).mockResolvedValue({
      materials: [{ cost_code: '03-01-025', category: 'MAT', actual_amount: '500.00',
        first_month: '2026-06', last_month: '2026-07' }],
    } as never)
    renderWithClient(<StaffingMatSummary project="tropical" />)
    expect(await screen.findByText('03-01-025 · MAT')).toBeInTheDocument()
  })
})
