import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getAssistantRecentChanges, getAssistantSources, getAssistantVaultNote } from './api'

function okJson(body: unknown) {
  return { ok: true, status: 200, statusText: 'OK', json: async () => body }
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

describe('assistant client — request URLs + role header', () => {
  it('builds GET /api/assistant/sources with q + limit', async () => {
    fetchMock.mockResolvedValue(okJson({ sources: [], count: 0, limit: 10, truncated: false }))
    await getAssistantSources('procore invoice', { limit: 10 })
    const [url] = lastCall(fetchMock)
    expect(url).toBe('/api/assistant/sources?q=procore+invoice&limit=10')
  })

  it('builds GET /api/assistant/recent-changes with limit', async () => {
    fetchMock.mockResolvedValue(okJson({ changes: [], count: 0, limit: 25, truncated: false }))
    await getAssistantRecentChanges(25)
    const [url] = lastCall(fetchMock)
    expect(url).toBe('/api/assistant/recent-changes?limit=25')
  })

  it('encodes the note_rel_path for GET /api/assistant/vault-note', async () => {
    fetchMock.mockResolvedValue(okJson({ path: 'Projects/Note One.md', content: '' }))
    await getAssistantVaultNote('Projects/Note One.md', 500)
    const [url] = lastCall(fetchMock)
    expect(url).toBe('/api/assistant/vault-note?note_rel_path=Projects%2FNote+One.md&max_chars=500')
  })

  it('sends the X-HB-UI-Role header on requests', async () => {
    fetchMock.mockResolvedValue(okJson({ sources: [], count: 0, limit: 10, truncated: false }))
    await getAssistantSources('x')
    const [, init] = lastCall(fetchMock)
    const headers = init.headers as Headers
    expect(headers.get('X-HB-UI-Role')).toBeTruthy()
  })
})
