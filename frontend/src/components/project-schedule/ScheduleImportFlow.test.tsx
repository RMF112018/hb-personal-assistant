import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleImportFlow } from './ScheduleImportFlow'

const uploadMock = vi.fn()
const commitMock = vi.fn()
const statusMock = vi.fn()
const retryMock = vi.fn()

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      uploadProjectScheduleImportPreview: (...args: unknown[]) => uploadMock(...args),
      commitProjectScheduleImport: (...args: unknown[]) => commitMock(...args),
      getProjectScheduleImportStatus: (...args: unknown[]) => statusMock(...args),
      retryProjectScheduleImportCpm: (...args: unknown[]) => retryMock(...args),
    },
  }
})

const packagePreview = {
  import_id: 'imp-1',
  source_filename: 'TWNU18.zip',
  package_mode: 'zip_package',
  assembly_mode: 'unified_companion_package',
  source_format: 'primavera_xer',
  data_date: '2026-06-23',
  activity_count: 1378,
  relationship_count: 3718,
  code_count: 5171,
  udf_count: 4311,
  equivalence_report: { status: 'compatible', companion_count: 1, equivalent_companion_count: 1 },
  files: [
    {
      filename: 'TWNU18.xer',
      source_format: 'primavera_xer',
      parse_status: 'parsed',
      detected_activities: 1378,
      detected_baseline_projects: 0,
      warnings: [],
    },
    {
      filename: 'notes.txt',
      source_format: 'unknown',
      parse_status: 'ignored',
      detected_activities: 0,
      detected_baseline_projects: 0,
      warnings: [{ code: 'unsupported_package_file_ignored' }],
    },
  ],
  baseline_project_candidates: [
    { project_name: 'BL-OWN', activity_count: 1177, source_format: 'primavera_pmxml', project_id: 'BL1' },
  ],
  trust_preview: { warnings: [] },
}

function renderFlow(onCommitSuccess = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ScheduleImportFlow projectKey="tropical" onCommitSuccess={onCommitSuccess} />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('ScheduleImportFlow', () => {
  beforeEach(() => {
    uploadMock.mockReset()
    commitMock.mockReset()
    statusMock.mockReset()
    retryMock.mockReset()
    statusMock.mockResolvedValue({
      stages: [{ stage: 'cpm_recompute', label: 'CPM', status: 'complete' }],
      cpm: { cpm_recompute_status: 'complete' },
    })
  })

  it('renders preview panel with files counts baselines and equivalence', async () => {
    uploadMock.mockResolvedValue(packagePreview)
    renderFlow()
    const input = screen.getByLabelText(/Upload Primavera XER/i)
    fireEvent.change(input, { target: { files: [new File(['zip'], 'TWNU18.zip')] } })
    await waitFor(() => expect(uploadMock).toHaveBeenCalled())
    expect(await screen.findByTestId('schedule-import-preview-panel')).toBeInTheDocument()
    expect(screen.getByText(/Supported schedule files/i)).toBeInTheDocument()
    expect(screen.getAllByText(/1378/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Linked baseline candidates/i)).toBeInTheDocument()
    expect(screen.getByText(/Canonical merge/i)).toBeInTheDocument()
  })

  it('keeps technical details collapsed by default', async () => {
    uploadMock.mockResolvedValue(packagePreview)
    renderFlow()
    fireEvent.change(screen.getByLabelText(/Upload Primavera XER/i), {
      target: { files: [new File(['zip'], 'TWNU18.zip')] },
    })
    await screen.findByTestId('schedule-import-technical-details')
    const details = screen.getByTestId('schedule-import-technical-details')
    expect(details).not.toHaveAttribute('open')
  })

  it('disables file input while preview is loading', async () => {
    let resolveUpload: (v: unknown) => void = () => {}
    uploadMock.mockReturnValue(new Promise((r) => { resolveUpload = r }))
    renderFlow()
    const input = screen.getByLabelText(/Upload Primavera XER/i) as HTMLInputElement
    fireEvent.change(input, {
      target: { files: [new File(['zip'], 'TWNU18.zip')] },
    })
    expect(input).toBeDisabled()
    resolveUpload(packagePreview)
    await waitFor(() => expect(input).not.toBeDisabled())
  })

  it('shows partial result when CPM failed', async () => {
    uploadMock.mockResolvedValue(packagePreview)
    commitMock.mockResolvedValue({
      import_id: 'imp-1',
      schedule_version_key: 'svk-1',
      activity_count: 1378,
      relationship_count: 3718,
      cpm_recompute_status: 'failed',
      cpm_failure_reason: 'synthetic',
    })
    statusMock.mockResolvedValue({
      stages: [{ stage: 'cpm_recompute', status: 'failed' }],
      cpm: { cpm_recompute_status: 'failed' },
    })
    renderFlow()
    fireEvent.change(screen.getByLabelText(/Upload Primavera XER/i), {
      target: { files: [new File(['zip'], 'TWNU18.zip')] },
    })
    await screen.findByTestId('schedule-import-commit')
    fireEvent.click(screen.getByTestId('schedule-import-commit'))
    const result = await screen.findByTestId('schedule-import-commit-result')
    expect(result).toHaveAttribute('data-overall-status', 'partial')
    expect(screen.getByText(/Import needs attention/i)).toBeInTheDocument()
    expect(screen.getByTestId('schedule-import-retry')).toBeInTheDocument()
  })

  it('does not show retry when CPM complete', async () => {
    uploadMock.mockResolvedValue(packagePreview)
    commitMock.mockResolvedValue({
      import_id: 'imp-1',
      schedule_version_key: 'svk-1',
      activity_count: 1378,
      cpm_recompute_status: 'complete',
    })
    renderFlow()
    fireEvent.change(screen.getByLabelText(/Upload Primavera XER/i), {
      target: { files: [new File(['zip'], 'TWNU18.zip')] },
    })
    await screen.findByTestId('schedule-import-commit')
    fireEvent.click(screen.getByTestId('schedule-import-commit'))
    await screen.findByTestId('schedule-import-commit-result')
    expect(screen.queryByTestId('schedule-import-retry')).not.toBeInTheDocument()
  })

  it('calls onCommitSuccess after commit', async () => {
    uploadMock.mockResolvedValue(packagePreview)
    const onCommitSuccess = vi.fn()
    commitMock.mockResolvedValue({ import_id: 'imp-1', cpm_recompute_status: 'complete', activity_count: 2 })
    renderFlow(onCommitSuccess)
    fireEvent.change(screen.getByLabelText(/Upload Primavera XER/i), {
      target: { files: [new File(['zip'], 'TWNU18.zip')] },
    })
    await screen.findByTestId('schedule-import-commit')
    fireEvent.click(screen.getByTestId('schedule-import-commit'))
    await waitFor(() => expect(onCommitSuccess).toHaveBeenCalled())
  })
})
