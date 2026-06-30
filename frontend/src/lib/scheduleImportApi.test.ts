import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  commitProjectScheduleImport,
  getProjectScheduleImportStatus,
  retryProjectScheduleImportCpm,
  uploadProjectScheduleImportPreview,
} from './api'

function jsonResponse(body: unknown = {}) {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
  } as Response
}

describe('schedule import API helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('preview helper sends FormData to project-scoped endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ import_id: 'abc123' }))
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['xer'], 'demo.xer', { type: 'application/octet-stream' })
    await uploadProjectScheduleImportPreview('tropical', file)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/projects/tropical/schedule/import-preview')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    const form = init.body as FormData
    expect(form.get('file')).toBe(file)
  })

  it('commit helper posts JSON body with confirm true', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ import_id: 'abc123' }))
    vi.stubGlobal('fetch', fetchMock)

    await commitProjectScheduleImport('tropical', 'abc123')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/projects/tropical/schedule/import-commit')
    expect(init.method).toBe('POST')
    const body = JSON.parse(String(init.body))
    expect(body).toMatchObject({
      import_id: 'abc123',
      project_key: 'tropical',
      confirm: true,
    })
  })

  it('status helper calls import status route', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ stages: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await getProjectScheduleImportStatus('tropical', 'imp-1')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects/tropical/schedule/imports/imp-1/status')
  })

  it('retry helper calls recompute-cpm route', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ cpm_recompute_status: 'complete' }))
    vi.stubGlobal('fetch', fetchMock)

    await retryProjectScheduleImportCpm('tropical', 'imp-1')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects/tropical/schedule/imports/imp-1/recompute-cpm')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
  })
})
