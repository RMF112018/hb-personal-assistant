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

  it('shows 50 MB upload label with XER and zip-package support', () => {
    renderPage()
    expect(
      screen.getByText(
        /Upload Primavera XER, Primavera XML\/PMXML, Microsoft Project XML, or mapped CSV — or a \.zip\s+package of those files — max 50 MB/i,
      ),
    ).toBeInTheDocument()
  })

  it('accepts xer and zip in file input', () => {
    renderPage()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.accept).toContain('.xer')
    expect(input.accept).toContain('.xml')
    expect(input.accept).toContain('.pmxml')
    expect(input.accept).toContain('.csv')
    expect(input.accept).toContain('.zip')
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

  it('preview card shows preview-bound project after picker changes', async () => {
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
      schedule_name: 'TWNU18',
    })
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'minimal.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/TWNU18/)).toBeInTheDocument())
    const select = screen.getByRole('combobox', { name: /project/i })
    fireEvent.change(select, { target: { value: 'rybovich' } })
    await waitFor(() => expect(screen.queryByText(/TWNU18/)).not.toBeInTheDocument())
  })

  it('commit uses preview-bound project key', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'xer-commit',
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
    commitMock.mockResolvedValue({
      import_id: 'xer-commit',
      project_key: 'tropical',
      schedule_version_key: 'tropical|TWNU18|2026-01-01',
      schedule_identity_key: 'schedule-ident-1',
      identity_match: {
        match_status: 'resolved',
        match_type: 'exact_activity_fingerprint',
        requires_review: false,
      },
      comparison_basis: {
        identity_safe: true,
      },
    })
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'minimal.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/Commit import to database/i)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Commit import to database/i }))
    await waitFor(() =>
      expect(commitMock).toHaveBeenCalledWith('xer-commit', 'tropical', null, false),
    )
    expect(await screen.findByText(/Schedule identity/i)).toBeInTheDocument()
    expect(screen.getByText(/identity-safe prior available/i)).toBeInTheDocument()
  })

  it('shows safe copy for persistence failure', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'xer-fail',
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
    commitMock.mockRejectedValue(
      new ScheduleApiError(
        'schedule_import_persistence_failed',
        {
          code: 'schedule_import_persistence_failed',
          source_format: 'primavera_xer',
          project_key: 'tropical',
        },
        409,
      ),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'minimal.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/Commit import to database/i)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Commit import to database/i }))
    await waitFor(() => {
      expect(
        screen.getByText(/could not be saved completely/i),
      ).toBeInTheDocument()
    })
  })

  it('preview supersede sends confirmSupersede and preserves project selection', async () => {
    uploadMock
      .mockRejectedValueOnce(
        new ScheduleApiError(
          'duplicate_schedule_version',
          {
            code: 'duplicate_schedule_version',
            schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
            activity_count: 1378,
            relationship_count: 3718,
            view_path: '/schedules/activities?version=tropical',
          },
          409,
        ),
      )
      .mockResolvedValueOnce({
        import_id: 'supersede-preview',
        activity_count: 1378,
        relationship_count: 3718,
        source_format: 'primavera_xer',
        cost_loaded_status: 'not_cost_loaded',
        wbs_count: 10,
        calendar_count: 3,
        validation_findings: [],
        requires_column_mapping: false,
        project_key: 'tropical',
      })
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'TWNU18.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/already imported/i)).toBeInTheDocument())
    const select = screen.getByRole('combobox', { name: /project/i })
    expect(select).toHaveValue('tropical')
    fireEvent.click(screen.getByRole('button', { name: /Preview supersede/i }))
    await waitFor(() =>
      expect(uploadMock).toHaveBeenLastCalledWith(file, 'tropical', null, true),
    )
    expect(select).toHaveValue('tropical')
  })

  it('after supersede preview commit button sends confirmSupersede', async () => {
    uploadMock
      .mockRejectedValueOnce(
        new ScheduleApiError(
          'duplicate_schedule_version',
          {
            code: 'duplicate_schedule_version',
            schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
            activity_count: 1378,
            relationship_count: 3718,
            view_path: '/schedules/activities?version=tropical',
          },
          409,
        ),
      )
      .mockResolvedValueOnce({
        import_id: 'supersede-preview',
        activity_count: 1378,
        relationship_count: 3718,
        source_format: 'primavera_xer',
        cost_loaded_status: 'not_cost_loaded',
        wbs_count: 10,
        calendar_count: 3,
        validation_findings: [],
        requires_column_mapping: false,
        project_key: 'tropical',
      })
    commitMock.mockResolvedValue({
      import_id: 'supersede-preview',
      project_key: 'tropical',
      schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
      supersede_performed: true,
    })
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'TWNU18.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/already imported/i)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Preview supersede/i }))
    await waitFor(() => {
      expect(
        screen.getByText(/will supersede the existing schedule version/i),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /Commit supersede import to database/i }),
      ).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /Commit supersede import to database/i }))
    await waitFor(() =>
      expect(commitMock).toHaveBeenCalledWith('supersede-preview', 'tropical', null, true),
    )
  })

  it('commit duplicate 409 shows supersede-required message', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'dup-commit',
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
    commitMock.mockRejectedValue(
      new ScheduleApiError(
        'duplicate_schedule_version',
        {
          code: 'duplicate_schedule_version',
          schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
          activity_count: 1378,
          relationship_count: 3718,
          view_path: '/schedules/activities?version=tropical',
        },
        409,
      ),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'minimal.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/Commit import to database/i)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Commit import to database/i }))
    await waitFor(() => {
      expect(
        screen.getByText(/Use the supersede flow to replace it/i),
      ).toBeInTheDocument()
    })
  })

  it('commit supersede state mismatch shows structured backend message', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'supersede-preview',
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
    commitMock.mockRejectedValue(
      new ScheduleApiError(
        'schedule_supersede_state_mismatch',
        {
          code: 'schedule_supersede_state_mismatch',
          schedule_version_key: 'tropical|TWNU18|2026-05-26T08:00:00',
          preview_confirm_supersede: true,
          commit_confirm_supersede: true,
        },
        409,
      ),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['ERMHDR'], 'minimal.xer', { type: 'application/octet-stream' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/Commit import to database/i)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Commit import to database/i }))
    await waitFor(() => {
      expect(screen.getByText(/supersede confirmation no longer matches/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/file format/i)).not.toBeInTheDocument()
  })

  it('renders zip-package manifest with selected current, baselines, and ignored files', async () => {
    uploadMock.mockResolvedValue({
      import_id: 'pkg-1',
      activity_count: 3953,
      relationship_count: 100,
      source_format: 'primavera_xer',
      cost_loaded_status: 'not_cost_loaded',
      wbs_count: 10,
      calendar_count: 2,
      validation_findings: [],
      requires_column_mapping: false,
      project_key: 'tropical',
      schedule_name: 'CARETTAU27',
      package_mode: 'zip_package',
      assembly_mode: 'unified_companion_package',
      equivalence_report: {
        status: 'compatible',
        companion_count: 1,
        equivalent_companion_count: 1,
      },
      field_family_lineage: [
        {
          field_family: 'current_activities',
          source_format: 'primavera_xer',
          merge_strategy: 'primary_authoritative',
          records_contributed: 3953,
        },
        {
          field_family: 'current_udfs',
          source_format: 'primavera_pmxml',
          merge_strategy: 'companion_additive',
          records_contributed: 12,
        },
      ],
      files: [
        {
          filename: 'CARETTAU27-wBL.xer',
          source_format: 'primavera_xer',
          parse_status: 'parsed',
          detected_activities: 3953,
          detected_baseline_projects: 0,
          warnings: [],
        },
        {
          filename: 'CARETTAU27.xml',
          source_format: 'primavera_pmxml',
          parse_status: 'parsed',
          detected_activities: 3953,
          detected_baseline_projects: 1,
          warnings: [],
        },
      ],
      current_project_candidates: [],
      baseline_project_candidates: [
        {
          source_file_id: 'pf-2',
          project_id: 'BL1',
          project_name: 'Approved Baseline',
          activity_count: 120,
          source_format: 'primavera_pmxml',
        },
      ],
      warnings: [
        { code: 'unsupported_package_file_ignored', filename: 'readme.txt', message: 'unsupported file ignored' },
      ],
      capabilities: {},
    })
    renderPage()
    await selectTropicalProject()
    const file = new File(['PK'], 'Caretta.zip', { type: 'application/zip' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/ZIP package — 2 files/i)).toBeInTheDocument())
    expect(screen.getByText(/XER preferred over XML/i)).toBeInTheDocument()
    expect(screen.getByText(/Assembly: unified_companion_package/i)).toBeInTheDocument()
    expect(screen.getByText(/current_udfs/)).toBeInTheDocument()
    expect(screen.getByText(/CARETTAU27-wBL\.xer/)).toBeInTheDocument()
    expect(screen.getByText(/Approved Baseline/)).toBeInTheDocument()
    expect(screen.getByText(/readme\.txt/)).toBeInTheDocument()
  })

  it('blocks ambiguous packages with multiple current schedules and lists candidates', async () => {
    uploadMock.mockRejectedValue(
      new ScheduleApiError(
        'schedule_package_multiple_current_candidates',
        {
          code: 'schedule_package_multiple_current_candidates',
          block_reason: 'different_normalized_data_date',
          candidates: [
            {
              source_file_id: 'pf-1',
              project_id: 'CURJUN',
              project_name: 'June Schedule',
              data_date: '2026-06-01 08:00',
              activity_count: 10,
              source_format: 'primavera_pmxml',
            },
            {
              source_file_id: 'pf-2',
              project_id: 'CURJUL',
              project_name: 'July Schedule',
              data_date: '2026-07-01 08:00',
              activity_count: 12,
              source_format: 'primavera_pmxml',
            },
          ],
        },
        409,
      ),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['PK'], 'ambiguous.zip', { type: 'application/zip' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(screen.getByText(/Multiple current schedules found/i)).toBeInTheDocument()
      expect(screen.getByText(/different data dates/i)).toBeInTheDocument()
      expect(screen.getByText(/June Schedule/)).toBeInTheDocument()
      expect(screen.getByText(/July Schedule/)).toBeInTheDocument()
    })
  })

  it('shows curated copy for a zip-package safety error', async () => {
    uploadMock.mockRejectedValue(
      new ScheduleApiError('schedule_zip_too_large', { code: 'schedule_zip_too_large' }, 400),
    )
    renderPage()
    await selectTropicalProject()
    const file = new File(['PK'], 'big.zip', { type: 'application/zip' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(screen.getByText(/too large once decompressed \(150 MB limit\)/i)).toBeInTheDocument()
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
