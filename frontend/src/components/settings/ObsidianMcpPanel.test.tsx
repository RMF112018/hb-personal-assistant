/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable-next-line @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- vitest mock typing in this test harness causes spurious tsc errors; the vitest runner still validates at test time.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ObsidianMcpPanel } from './ObsidianMcpPanel'

// No secret/token VALUE should ever reach the rendered DOM. (The panel legitimately renders a
// "Bearer token" field label, so we check for token-value markers, not the word "Bearer".)
const FORBIDDEN = [
  'access_token',
  'refresh_token',
  'client_secret',
  'eyJ',
  'BEGIN PRIVATE KEY',
] as const

function assertNoForbidden(bodyText: string) {
  for (const f of FORBIDDEN) {
    expect(bodyText).not.toContain(f)
  }
}

// --- API mocks -------------------------------------------------------------
const getObsidianMcpConfig = vi.fn()
const getObsidianMcpChatGPT = vi.fn()
const getObsidianMcpGrokConfig = vi.fn()
const getObsidianMcpMutations = vi.fn()
const getObsidianMcpOAuth = vi.fn()
const getObsidianMcpLlmChatStatus = vi.fn()
const getObsidianMcpReadReceipts = vi.fn()
const getObsidianMcpStatus = vi.fn()
const getObsidianMcpTools = vi.fn()
const patchObsidianMcpConfig = vi.fn()
const getObsidianMcpSourceIndexStatus = vi.fn()
const getObsidianMcpSourceWatchStatus = vi.fn()
const noop = vi.fn(async () => ({}))

vi.mock('../../lib/api', () => ({
  disableObsidianMcp: (...a: any[]) => noop(...a),
  enableObsidianMcp: (...a: any[]) => noop(...a),
  getObsidianMcpConfig: (...a: any[]) => getObsidianMcpConfig(...a),
  getObsidianMcpChatGPT: (...a: any[]) => getObsidianMcpChatGPT(...a),
  getObsidianMcpGrokConfig: (...a: any[]) => getObsidianMcpGrokConfig(...a),
  getObsidianMcpMutations: (...a: any[]) => getObsidianMcpMutations(...a),
  getObsidianMcpOAuth: (...a: any[]) => getObsidianMcpOAuth(...a),
  getObsidianMcpLlmChatStatus: (...a: any[]) => getObsidianMcpLlmChatStatus(...a),
  getObsidianMcpReadReceipts: (...a: any[]) => getObsidianMcpReadReceipts(...a),
  getObsidianMcpStatus: (...a: any[]) => getObsidianMcpStatus(...a),
  getObsidianMcpTools: (...a: any[]) => getObsidianMcpTools(...a),
  patchObsidianMcpConfig: (...a: any[]) => patchObsidianMcpConfig(...a),
  restartObsidianMcp: (...a: any[]) => noop(...a),
  runObsidianMcpChatGPTReadiness: (...a: any[]) => noop(...a),
  runObsidianMcpHealthCheck: (...a: any[]) => noop(...a),
  runObsidianMcpWriteReadiness: (...a: any[]) => noop(...a),
  testObsidianMcpListDirectory: (...a: any[]) => noop(...a),
  testObsidianMcpReadFile: (...a: any[]) => noop(...a),
  testObsidianMcpSearch: (...a: any[]) => noop(...a),
  testObsidianMcpWriteSmoke: (...a: any[]) => noop(...a),
  getObsidianMcpSourceIndexStatus: (...a: any[]) => getObsidianMcpSourceIndexStatus(...a),
  rebuildObsidianMcpSourceIndex: (...a: any[]) => noop(...a),
  generateObsidianMcpSourceCard: (...a: any[]) => noop(...a),
  summarizeObsidianMcpSource: (...a: any[]) => noop(...a),
  refreshObsidianMcpStaleSourceNotes: (...a: any[]) => noop(...a),
  testObsidianMcpModel: (...a: any[]) => noop(...a),
  getObsidianMcpSourceWatchStatus: (...a: any[]) => getObsidianMcpSourceWatchStatus(...a),
  startObsidianMcpSourceWatch: (...a: any[]) => noop(...a),
  stopObsidianMcpSourceWatch: (...a: any[]) => noop(...a),
  restartObsidianMcpSourceWatch: (...a: any[]) => noop(...a),
  testObsidianMcpSourceWatchEvent: (...a: any[]) => noop(...a),
  recoverObsidianMcpSourceWatchStuck: (...a: any[]) => noop(...a),
}))

const BASE_CONFIG = {
  enabled: true,
  external_source_index_enabled: true,
  external_source_watch_enabled: false,
  external_source_scan_max_files: 5000,
  watch_poll_interval_seconds: 30,
  watch_debounce_seconds: 1.5,
  external_sources: [
    { source_root_key: 'twn', path: '/Users/test/twn', enabled: true, sensitive: false, source_kind: 'external_file' },
  ],
}

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })
}

function renderPanel(watching = false) {
  getObsidianMcpConfig.mockResolvedValue({ config: BASE_CONFIG })
  getObsidianMcpStatus.mockResolvedValue({})
  getObsidianMcpTools.mockResolvedValue({ tools: [] })
  getObsidianMcpGrokConfig.mockResolvedValue({})
  getObsidianMcpMutations.mockResolvedValue({ mutations: [] })
  getObsidianMcpOAuth.mockResolvedValue({})
  getObsidianMcpReadReceipts.mockResolvedValue({ read_receipts: [] })
  getObsidianMcpChatGPT.mockResolvedValue({})
  getObsidianMcpLlmChatStatus.mockResolvedValue({})
  getObsidianMcpSourceIndexStatus.mockResolvedValue({ sources_total: 0 })
  getObsidianMcpSourceWatchStatus.mockResolvedValue({ running: watching, mode: 'watchdog', roots: [] })
  patchObsidianMcpConfig.mockImplementation(async (patch: any) => ({ config: { ...BASE_CONFIG, ...patch } }))
  const client = makeClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ObsidianMcpPanel />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// Wait for the config-driven draft to be seeded (existing root rendered).
async function waitForSeed() {
  await waitFor(() =>
    expect((screen.getByLabelText('root key 0') as HTMLInputElement).value).toBe('twn'),
  )
}

function lastPatch() {
  return patchObsidianMcpConfig.mock.calls.at(-1)?.[0]
}

describe('ObsidianMcpPanel — external source roots', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the external source roots editor with an add-root form', async () => {
    renderPanel()
    expect(await screen.findByText('External source roots')).toBeInTheDocument()
    expect(screen.getByLabelText('new root key')).toBeInTheDocument()
    expect(screen.getByLabelText('new root path')).toBeInTheDocument()
    expect(screen.getByText('Save roots')).toBeInTheDocument()
  })

  it('renders existing configured roots as editable rows', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    expect((screen.getByLabelText('root path 0') as HTMLInputElement).value).toBe('/Users/test/twn')
    expect((screen.getByLabelText('root enabled 0') as HTMLInputElement).checked).toBe(true)
  })

  it('adding a valid root and saving calls patch with the expected external_sources payload', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    fireEvent.change(screen.getByLabelText('new root key'), { target: { value: 'manual-test' } })
    fireEvent.change(screen.getByLabelText('new root path'), { target: { value: '/tmp/hb-source-summary-test-root' } })
    fireEvent.click(screen.getByText('Add'))
    fireEvent.click(screen.getByText(/Save roots/))
    await waitFor(() => expect(patchObsidianMcpConfig).toHaveBeenCalled())
    expect(lastPatch().external_sources).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source_root_key: 'manual-test',
          path: '/tmp/hb-source-summary-test-root',
          enabled: true,
          sensitive: false,
          source_kind: 'external_file',
        }),
      ]),
    )
  })

  it('rejects a relative path client-side and does not call patch', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    fireEvent.change(screen.getByLabelText('new root key'), { target: { value: 'rel' } })
    fireEvent.change(screen.getByLabelText('new root path'), { target: { value: 'relative/path' } })
    fireEvent.click(screen.getByText('Add'))
    expect(await screen.findByText(/must be absolute/)).toBeInTheDocument()
    expect(patchObsidianMcpConfig).not.toHaveBeenCalled()
  })

  it('rejects a duplicate root key client-side and does not call patch', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    fireEvent.change(screen.getByLabelText('new root key'), { target: { value: 'twn' } })
    fireEvent.change(screen.getByLabelText('new root path'), { target: { value: '/Users/test/other' } })
    fireEvent.click(screen.getByText('Add'))
    expect(await screen.findByText(/Duplicate root key/)).toBeInTheDocument()
    expect(patchObsidianMcpConfig).not.toHaveBeenCalled()
  })

  it('disabling a root then saving sends enabled:false in the payload', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    fireEvent.click(screen.getByLabelText('root enabled 0'))
    fireEvent.click(screen.getByText(/Save roots/))
    await waitFor(() => expect(patchObsidianMcpConfig).toHaveBeenCalled())
    const twn = lastPatch().external_sources.find((r: any) => r.source_root_key === 'twn')
    expect(twn.enabled).toBe(false)
  })

  it('removing a root requires confirmation, then saving omits it from the payload', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    fireEvent.click(screen.getByText('Remove'))
    fireEvent.click(await screen.findByText('Confirm remove'))
    fireEvent.click(screen.getByText(/Save roots/))
    await waitFor(() => expect(patchObsidianMcpConfig).toHaveBeenCalled())
    expect(lastPatch().external_sources).toEqual([])
  })

  it('keeps the existing watcher lifecycle controls present', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    expect(screen.getByText('Test event')).toBeInTheDocument()
    expect(screen.getByText('Recover stuck')).toBeInTheDocument()
    expect(screen.getByText('Start')).toBeInTheDocument()
    expect(screen.getByText('Stop')).toBeInTheDocument()
  })

  it('does not leak secret material into the DOM', async () => {
    renderPanel()
    await screen.findByText('External source roots')
    await waitForSeed()
    assertNoForbidden(document.body.textContent || '')
  })
})

// Source Intelligence generation policy UI (A1.8).
function renderPanelWith(opts: { sourceIndex?: any; config?: any } = {}) {
  getObsidianMcpConfig.mockResolvedValue({ config: { ...BASE_CONFIG, ...(opts.config || {}) } })
  getObsidianMcpStatus.mockResolvedValue({})
  getObsidianMcpTools.mockResolvedValue({ tools: [] })
  getObsidianMcpGrokConfig.mockResolvedValue({})
  getObsidianMcpMutations.mockResolvedValue({ mutations: [] })
  getObsidianMcpOAuth.mockResolvedValue({})
  getObsidianMcpReadReceipts.mockResolvedValue({ read_receipts: [] })
  getObsidianMcpChatGPT.mockResolvedValue({})
  getObsidianMcpLlmChatStatus.mockResolvedValue({})
  getObsidianMcpSourceIndexStatus.mockResolvedValue(opts.sourceIndex || { sources_total: 0 })
  getObsidianMcpSourceWatchStatus.mockResolvedValue({ running: false, mode: 'watchdog', roots: [] })
  patchObsidianMcpConfig.mockImplementation(async (patch: any) => ({ config: { ...BASE_CONFIG, ...patch } }))
  const client = makeClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ObsidianMcpPanel />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ObsidianMcpPanel — source intelligence generation policy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the auto-generation toggles', async () => {
    renderPanelWith()
    expect(await screen.findByText('Auto-generate cards on index')).toBeInTheDocument()
    expect(screen.getByText('Auto-summarize on index')).toBeInTheDocument()
    expect(screen.getByText('Auto-refresh existing cards')).toBeInTheDocument()
  })

  it('keeps the manual source-id generate/summarize/refresh controls', async () => {
    renderPanelWith()
    await screen.findByText('Source Intelligence')
    expect(screen.getByText('Generate card')).toBeInTheDocument()
    expect(screen.getByText('Summarize')).toBeInTheDocument()
    expect(screen.getByText('Refresh stale notes')).toBeInTheDocument()
  })

  it('rebuild helper text reflects that card generation is ON', async () => {
    renderPanelWith({ config: { source_card_auto_generate_enabled: true } })
    await screen.findByText('Source Intelligence')
    expect(document.body.textContent).toContain('generates deterministic source cards')
    expect(document.body.textContent).toContain('Source Notes/')
  })

  it('rebuild helper text reflects that card generation is OFF', async () => {
    renderPanelWith({ config: { source_card_auto_generate_enabled: false } })
    await screen.findByText('Source Intelligence')
    expect(document.body.textContent).toContain('does not generate cards')
  })

  it('displays the card auto-max-per-drain control seeded from config', async () => {
    renderPanelWith({ config: { source_card_auto_max_per_drain: 25 } })
    await screen.findByText('Source Intelligence')
    await waitFor(() =>
      expect((screen.getByLabelText('Card auto max per drain') as HTMLInputElement).value).toBe('25'),
    )
  })

  it('submits the card auto-max-per-drain value on blur', async () => {
    renderPanelWith({ config: { source_card_auto_max_per_drain: 200 } })
    await screen.findByText('Source Intelligence')
    const input = await screen.findByLabelText('Card auto max per drain')
    await waitFor(() => expect((input as HTMLInputElement).value).toBe('200'))
    fireEvent.change(input, { target: { value: '25' } })
    fireEvent.blur(input)
    await waitFor(() => expect(patchObsidianMcpConfig).toHaveBeenCalled())
    expect(lastPatch()).toEqual(expect.objectContaining({ source_card_auto_max_per_drain: 25 }))
  })

  it('displays the excluded-path-parts control seeded from config', async () => {
    renderPanelWith({ config: { source_index_excluded_path_parts: ['node_modules', '.venv', 'dist'] } })
    await screen.findByText('Source Intelligence')
    await waitFor(() =>
      expect((screen.getByLabelText('Excluded path parts') as HTMLInputElement).value).toBe('node_modules, .venv, dist'),
    )
    expect(document.body.textContent).toContain('Broad roots can create')
  })

  it('submits edited excluded path parts as an array on blur', async () => {
    renderPanelWith({ config: { source_index_excluded_path_parts: ['node_modules'] } })
    await screen.findByText('Source Intelligence')
    const input = await screen.findByLabelText('Excluded path parts')
    await waitFor(() => expect((input as HTMLInputElement).value).toBe('node_modules'))
    fireEvent.change(input, { target: { value: 'node_modules, .venv , dist' } })
    fireEvent.blur(input)
    await waitFor(() => expect(patchObsidianMcpConfig).toHaveBeenCalled())
    expect(lastPatch()).toEqual(
      expect.objectContaining({ source_index_excluded_path_parts: ['node_modules', '.venv', 'dist'] }),
    )
  })

  it('shows generated-card and last-generation counts when the backend returns them', async () => {
    renderPanelWith({
      sourceIndex: {
        sources_total: 12, generated_card_count: 7, summarized_count: 3, stale_summary_count: 0,
        last_generation_at: '2026-06-29T10:00:00Z', last_generation_cards: '5', last_generation_summaries: '2',
      },
    })
    await screen.findByText('Source Intelligence')
    expect(screen.getByText('Generated cards')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('Last generation (cards/sum)')).toBeInTheDocument()
    expect(screen.getByText('5 / 2')).toBeInTheDocument()
  })
})
