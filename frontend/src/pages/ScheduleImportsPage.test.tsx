import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleImportsPage } from './ScheduleImportsPage'
import { ScheduleApiError, ScheduleNetworkError } from '../lib/api'

const uploadMock = vi.fn()
const commitMock = vi.fn()
const projectsMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleProjects: () => projectsMock(),
      uploadScheduleImportPreview: (...args: unknown[]) => uploadMock(...args),
      commitScheduleImport: (...args: unknown[]) => commitMock(...args),
    },
  }
})

async function selectTropicalProject() {
  const select = await screen.findByRole('combobox', { name: /project/i })
  await waitFor(() => {
    expect(select.querySelector('option[value="tropical"]')).toBeTruthy()
  })
  fireEvent.change(select, { target: { value: 'tropical' } })
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/schedules/imports', element: <ScheduleImportsPage /> }],
    { initialEntries: ['/schedules/imports'] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ScheduleImportsPage', () => {
  beforeEach(() => {
    uploadMock.mockReset()
    commitMock.mockReset()
    projectsMock.mockReset()
    projectsMock.mockResolvedValue({
      catalog_status: 'ok',
      projects: [
        {
          project_key: 'tropical',
          display_name: 'Tropical Wind',
          project_identity_label: 'tropical — Tropical Wind',
          selectable_for_import: true,
        },
        {
          project_key: 'rybovich',
          display_name: '25-745-01 - RYBOVICH-SAFE HARBOR',
          project_number: '25-745-01',
          procore_project_id: '3133242',
          project_identity_label:
            'rybovich — 25-745-01 - RYBOVICH-SAFE HARBOR · #25-745-01 · Procore 3133242 ⚠',
          identity_warning: 'duplicate_display_metadata_across_project_keys',
          selectable_for_import: true,
        },
      ],
    })
  })

  it('shows 50 MB upload label with XER support', () => {
    renderPage()
    expect(
      screen.getByText(
        /Upload Primavera XER, Primavera XML\/PMXML, Microsoft Project XML, or mapped CSV — max 50 MB/i,
      ),
    ).toBeInTheDocument()
  })

  it('accepts xer in file input', () => {
    renderPage()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.accept).toContain('.xer')
    expect(input.accept).toContain('.xml')
    expect(input.accept).toContain('.pmxml')
    expect(input.accept).toContain('.csv')
  })

  it('uploads xer with selected project', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'xer-abc',
      activity_count: 2,
      relationship_count: 1,
      source_format: 'primavera_xer',
      cost_loaded_status: 'not_cost_loaded',
      wbs_count: 1,
      calendar_count: 1,
      validation_findings: [],
      requires_column_mapping: false,
      project_key: 'tropical',
    })
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'minimal.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(file, 'tropical', null, false))
  })

  it('unsupported format copy mentions xer', async () => {
    uploadMock.mockRejectedValue(
      new ScheduleApiError('unsupported_schedule_format', { code: 'unsupported_schedule_format' }, 400),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(
        screen.getByText(
          /Unsupported schedule format\. Use Primavera XER, Primavera XML\/PMXML/i,
        ),
      ).toBeInTheDocument()
    })
  })

  it('renders display_name as import picker option text', async () => {
    renderPage()
    const tropical = await screen.findByRole('option', { name: 'Tropical Wind' })
    const rybovich = await screen.findByRole('option', {
      name: '25-745-01 - RYBOVICH-SAFE HARBOR',
    })
    expect(tropical).toHaveAttribute('value', 'tropical')
    expect(rybovich).toHaveAttribute('value', 'rybovich')
  })

  it('requires project selection before upload', async () => {
    renderPage()
    const file = new File(['<xml/>'], 'sample.xml', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(uploadMock).not.toHaveBeenCalled()
      expect(screen.getByText(/select an existing project/i)).toBeInTheDocument()
    })
  })

  it('uploads file with selected project', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'abc',
      activity_count: 2,
      relationship_count: 1,
      source_format: 'primavera_pmxml',
      cost_loaded_status: 'not_cost_loaded',
      wbs_count: 0,
      calendar_count: 0,
      validation_findings: [],
      requires_column_mapping: false,
      project_key: 'tropical',
    })
    renderPage()
    await selectTropicalProject()
    const file = new File(['<xml/>'], 'sample.xml', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(file, 'tropical', null, false))
  })

  it('renders duplicate preview with counts and link', async () => {
    uploadMock.mockRejectedValue(
      new ScheduleApiError(
        'duplicate_schedule_version',
        {
          code: 'duplicate_schedule_version',
          schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
          activity_count: 1378,
          relationship_count: 3718,
          view_path: '/schedules/activities?version=tropical%7CTWNU18%7C2026-05-26T08%3A00%3A00',
        },
        409,
      ),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['<xml/>'], 'TWNU18.xml', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(screen.getByText(/already imported/i)).toBeInTheDocument()
      expect(screen.getByText(/1378/)).toBeInTheDocument()
      expect(screen.getByText(/3718/)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /View existing activities/i })).toBeInTheDocument()
    })
  })

  it('shows schema-not-ready message from controlled API error', async () => {
    uploadMock.mockRejectedValue(
      new ScheduleApiError('schedule_schema_not_ready', { code: 'schedule_schema_not_ready' }, 503),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['<xml/>'], 'sample.xml', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(screen.getByText(/pending database migrations/i)).toBeInTheDocument()
    })
  })

  it('shows network error when upload cannot reach backend', async () => {
    uploadMock.mockRejectedValue(new ScheduleNetworkError())
    renderPage()
    await selectTropicalProject()
    const file = new File(['<xml/>'], 'sample.xml', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(screen.getByText(/could not reach the schedule import service/i)).toBeInTheDocument()
    })
  })

  it('shows previewing state while upload is in flight', async () => {
    let resolve!: (v: unknown) => void
    uploadMock.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['<xml/>'], 'sample.xml', { type: 'application/xml' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    expect(await screen.findByText(/Previewing schedule/i)).toBeInTheDocument()
    resolve({
      import_id: 'abc',
      activity_count: 1,
      relationship_count: 0,
      source_format: 'primavera_pmxml',
      cost_loaded_status: 'not_cost_loaded',
      wbs_count: 0,
      calendar_count: 0,
      validation_findings: [],
      requires_column_mapping: false,
    })
    await waitFor(() => expect(screen.queryByText(/Previewing schedule/i)).not.toBeInTheDocument())
  })
})