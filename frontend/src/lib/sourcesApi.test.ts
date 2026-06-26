import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getEnvironment,
  getGraphSourceAuthStatus,
  getGraphSourceStatus,
  getProcoreSourceStatus,
  getScheduleHealthData,
  getSchedulerStatus,
  getSourcesStatus,
  refreshSources,
  refreshSourcesDryRun,
  refreshSourcesLive,
  refreshSourcesLocal,
  type RefreshMode,
} from './api'
import { getErrorCopy } from './errorCopy'

function okJson(body: unknown) {
  return { ok: true, status: 200, statusText: 'OK', json: async () => body }
}

function errJson(status: number, statusText: string, body: unknown) {
  return { ok: false, status, statusText, json: async () => body }
}

function lastCall(mock: ReturnType<typeof vi.fn>): [string, RequestInit] {
  const call = mock.mock.calls[mock.mock.calls.length - 1]
  return [call[0] as string, (call[1] || {}) as RequestInit]
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('source-status client — response mapping', () => {
  it('maps GET /api/environment to a typed EnvironmentStatus', async () => {
    fetchMock.mockResolvedValue(
      okJson({ environment: 'dev', source_refresh_mode: 'mock_data', live_refresh: { enabled: false } }),
    )
    const result = await getEnvironment()
    expect(result.environment).toBe('dev')
    expect(result.source_refresh_mode).toBe('mock_data')
    expect(result.live_refresh?.enabled).toBe(false)
    const [url] = lastCall(fetchMock)
    expect(url).toBe('/api/environment')
  })

  it('maps GET /api/sources/status with graph/procore/scheduler summaries', async () => {
    fetchMock.mockResolvedValue(
      okJson({ environment: 'dev', graph: { system: 'microsoft_365_graph' }, procore: { system: 'procore' }, scheduler: { enabled: true } }),
    )
    const result = await getSourcesStatus()
    expect(result.graph?.system).toBe('microsoft_365_graph')
    expect(result.procore?.system).toBe('procore')
    expect(result.scheduler?.enabled).toBe(true)
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/status')
  })

  it('maps Graph + Procore per-source status (state + scope/mapping fields)', async () => {
    fetchMock.mockResolvedValue(
      okJson({ system: 'microsoft_365_graph', state: 'connected_valid', scope_presence: { missing: [], all_present: true } }),
    )
    const graph = await getGraphSourceStatus()
    expect(graph.state).toBe('connected_valid')
    expect(graph.scope_presence?.all_present).toBe(true)
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/graph/status')

    fetchMock.mockResolvedValue(
      okJson({ system: 'procore', state: 'not_configured', missing_config: true, missing_mapping: false }),
    )
    const procore = await getProcoreSourceStatus()
    expect(procore.state).toBe('not_configured')
    expect(procore.missing_config).toBe(true)
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/procore/status')
  })

  it('maps GET scheduler status', async () => {
    fetchMock.mockResolvedValue(
      okJson({ schedule_time_local: '20:00', timezone: 'America/New_York', live_reads_enabled: false, state_health: 'ok' }),
    )
    const result = await getSchedulerStatus()
    expect(result.schedule_time_local).toBe('20:00')
    expect(result.live_reads_enabled).toBe(false)
    expect(lastCall(fetchMock)[0]).toBe('/api/scheduler/daily-source-refresh/status')
  })

  it('sends the X-HB-UI-Role header on requests', async () => {
    fetchMock.mockResolvedValue(okJson({ environment: 'dev' }))
    await getEnvironment()
    const [, init] = lastCall(fetchMock)
    const headers = init.headers as Headers
    expect(headers.get('X-HB-UI-Role')).toBeTruthy()
  })
})

describe('source-refresh client — action URL selection', () => {
  beforeEach(() => {
    fetchMock.mockResolvedValue(okJson({ status: 'ok' }))
  })

  it('selects the dry-run endpoint (POST, no body)', async () => {
    await refreshSourcesDryRun()
    const [url, init] = lastCall(fetchMock)
    expect(url).toBe('/api/sources/refresh/dry-run')
    expect(init.method).toBe('POST')
    expect(init.body).toBeUndefined()
  })

  it('selects the local endpoint (POST, no body)', async () => {
    await refreshSourcesLocal()
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/refresh/local')
  })

  it('selects the live endpoint and carries the confirmation flag', async () => {
    await refreshSourcesLive(true)
    const [url, init] = lastCall(fetchMock)
    expect(url).toBe('/api/sources/refresh/live')
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"confirm":true}')
  })

  it('refreshSources dispatches by mode; only live carries confirm', async () => {
    await refreshSources('dry_run')
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/refresh/dry-run')
    expect(lastCall(fetchMock)[1].body).toBeUndefined()

    await refreshSources('local')
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/refresh/local')

    await refreshSources('live', { confirm: true })
    expect(lastCall(fetchMock)[0]).toBe('/api/sources/refresh/live')
    expect(lastCall(fetchMock)[1].body).toBe('{"confirm":true}')
  })

  it('throws on an unknown refresh mode', () => {
    const badMode = 'bogus' as unknown as RefreshMode
    expect(() => refreshSources(badMode)).toThrow(/unknown refresh mode/)
  })

  it('encodes query params for the auth status poll', async () => {
    fetchMock.mockResolvedValue(okJson({ flow_id: 'f1', status: 'pending' }))
    await getGraphSourceAuthStatus('f1/x')
    expect(lastCall(fetchMock)[0]).toContain('flow_id=f1%2Fx')
  })
})

describe('schedule health client', () => {
  it('encodes the health-data endpoint and optional project scope', async () => {
    fetchMock.mockResolvedValue(okJson({ schedule_version_key: 'twn|1071|2026-06-23 08:00' }))

    await getScheduleHealthData('twn|1071|2026-06-23 08:00', 'twn/project')

    expect(lastCall(fetchMock)[0]).toBe(
      '/api/schedules/versions/twn%7C1071%7C2026-06-23%2008%3A00/health-data?project_key=twn%2Fproject',
    )
  })
})

describe('source-status client — failure copy is user-safe', () => {
  it('maps a 404 not_found to friendly copy', async () => {
    fetchMock.mockResolvedValue(errJson(404, 'Not Found', { detail: 'not_found' }))
    await expect(getEnvironment()).rejects.toBeTruthy()
    let copy
    try {
      await getEnvironment()
    } catch (e) {
      copy = getErrorCopy(e)
    }
    expect(copy?.userMessage).toBe('This information is not available yet.')
  })

  it('maps a 500 to a generic safe message with no raw JSON', async () => {
    fetchMock.mockResolvedValue(errJson(500, 'Internal Server Error', { detail: 'db boom {trace}' }))
    let copy
    try {
      await getSourcesStatus()
    } catch (e) {
      copy = getErrorCopy(e)
    }
    expect(copy?.userMessage).toBe('We could not load this section.')
    expect(copy?.userMessage).not.toContain('{')
    expect(copy?.userMessage).not.toContain('trace')
  })

  it('maps a network failure to a generic safe message', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    let copy
    try {
      await getSchedulerStatus()
    } catch (e) {
      copy = getErrorCopy(e)
    }
    expect(copy?.userMessage).toBe('We could not load this section.')
  })
})
