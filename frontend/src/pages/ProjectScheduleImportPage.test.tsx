import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectScheduleImportPage } from './ProjectScheduleImportPage'
import { ProjectSchedulePage } from './ProjectSchedulePage'

const uploadMock = vi.fn()
const commitMock = vi.fn()
const statusMock = vi.fn()
const projectsMock = vi.fn()
const summaryMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getProjects: () => projectsMock(),
      uploadProjectScheduleImportPreview: (...args: unknown[]) => uploadMock(...args),
      commitProjectScheduleImport: (...args: unknown[]) => commitMock(...args),
      getProjectScheduleImportStatus: (...args: unknown[]) => statusMock(...args),
      getProjectScheduleSummary: (...args: unknown[]) => summaryMock(...args),
    },
  }
})

const projectsResponse = {
  projects: [
    {
      project_key: 'tropical',
      display_name: 'Tropical Wind',
      project_identity_label: 'tropical — Tropical Wind',
    },
  ],
}

function renderImportPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/projects/:projectKey/schedule/import', element: <ProjectScheduleImportPage /> }],
    { initialEntries: ['/projects/tropical/schedule/import'] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

function renderSchedulePage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/projects/:projectKey/schedule', element: <ProjectSchedulePage /> }],
    { initialEntries: ['/projects/tropical/schedule'] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ProjectScheduleImportPage', () => {
  beforeEach(() => {
    uploadMock.mockReset()
    commitMock.mockReset()
    statusMock.mockReset()
    projectsMock.mockReset()
    summaryMock.mockReset()
    projectsMock.mockResolvedValue(projectsResponse)
    statusMock.mockResolvedValue({
      stages: [{ stage: 'cpm_recompute', label: 'Computed CPM recompute', status: 'complete' }],
      cpm: { cpm_recompute_status: 'complete' },
    })
  })

  it('renders project-scoped import page without project picker', async () => {
    renderImportPage()
    expect(await screen.findByText(/Upload schedule update/i)).toBeInTheDocument()
    expect((await screen.findAllByText(/Tropical Wind/i)).length).toBeGreaterThan(0)
    expect(screen.queryByRole('combobox', { name: /project/i })).not.toBeInTheDocument()
  })

  it('uploads via project-scoped preview endpoint', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'imp-1',
      activity_count: 2,
      source_format: 'primavera_xer',
      trust_preview: { warnings: [{ code: 'likely_new_schedule_series', message: 'Review identity after commit.' }] },
    })
    renderImportPage()
    const input = await screen.findByLabelText(/Upload Primavera XER/i)
    const file = new File(['xer'], 'minimal.xer', { type: 'application/octet-stream' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(uploadMock).toHaveBeenCalledWith('tropical', file, null, false)
    })
    expect(await screen.findByText(/Identity \/ trust preview/i)).toBeInTheDocument()
  })

  it('shows processing checklist after commit', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'imp-2',
      activity_count: 2,
      source_format: 'primavera_xer',
      trust_preview: { warnings: [] },
    })
    commitMock.mockResolvedValue({
      import_id: 'imp-2',
      cpm_recompute_status: 'complete',
      pipeline: {
        stages: [{ stage: 'cpm_recompute', label: 'Computed CPM recompute', status: 'complete' }],
      },
    })
    renderImportPage()
    const input = await screen.findByLabelText(/Upload Primavera XER/i)
    fireEvent.change(input, { target: { files: [new File(['xer'], 'minimal.xer')] } })
    await screen.findByText(/Preview schedule update and commit/i)
    fireEvent.click(screen.getByText(/Preview schedule update and commit/i))
    expect(await screen.findByText(/Processing checklist/i)).toBeInTheDocument()
    expect(screen.getByText(/Return to Project Schedule/i)).toBeInTheDocument()
  })
})

describe('ProjectSchedulePage import action', () => {
  beforeEach(() => {
    projectsMock.mockResolvedValue(projectsResponse)
    summaryMock.mockResolvedValue({
      status: 'ok',
      as_of_date: '2026-07-03',
      schedule_story: { headline: 'Schedule update ready' },
      current_schedule: { friendly_label: 'Jul 3 update', data_date: '2026-07-03' },
      previous_update: { available: false },
      readiness: { items: [] },
      command_summary: {},
      remaining_health: { float_pressure: {} },
      computed_cpm: {},
      critical_path: {},
      change_impact: { direct_remaining_changes: {} },
      trend_summary: {},
      trend_series: { metrics: [] },
      schedule_trust: {},
      identity_review: {},
      baseline_summary: {},
      review_drilldowns: {},
      change_driver_analysis: { prior_update: { available: false } },
      review_workbench: {},
      source_float_summary: {},
      computed_cpm_summary: {},
      technical_links: {},
      actions: { preview: [], all_items: [] },
    })
  })

  it('shows Import Schedule action on hub page', async () => {
    renderSchedulePage()
    expect(await screen.findByRole('link', { name: /Import Schedule/i })).toHaveAttribute(
      'href',
      '/projects/tropical/schedule/import',
    )
  })
})