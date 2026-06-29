/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from 'react'
import { Copy, Play, RefreshCw, ShieldCheck } from 'lucide-react'

import {
  disableObsidianMcp,
  enableObsidianMcp,
  getObsidianMcpConfig,
  getObsidianMcpChatGPT,
  getObsidianMcpGrokConfig,
  getObsidianMcpMutations,
  getObsidianMcpOAuth,
  getObsidianMcpLlmChatStatus,
  getObsidianMcpReadReceipts,
  getObsidianMcpStatus,
  getObsidianMcpTools,
  patchObsidianMcpConfig,
  restartObsidianMcp,
  runObsidianMcpChatGPTReadiness,
  runObsidianMcpHealthCheck,
  runObsidianMcpWriteReadiness,
  testObsidianMcpListDirectory,
  testObsidianMcpReadFile,
  testObsidianMcpSearch,
  testObsidianMcpWriteSmoke,
  getObsidianMcpSourceIndexStatus,
  rebuildObsidianMcpSourceIndex,
  generateObsidianMcpSourceCard,
  summarizeObsidianMcpSource,
  refreshObsidianMcpStaleSourceNotes,
  testObsidianMcpModel,
  getObsidianMcpSourceWatchStatus,
  startObsidianMcpSourceWatch,
  stopObsidianMcpSourceWatch,
  restartObsidianMcpSourceWatch,
  testObsidianMcpSourceWatchEvent,
  recoverObsidianMcpSourceWatchStuck,
} from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { ErrorState } from '../common/ErrorState'
import { TechnicalDetails } from '../common/TechnicalDetails'

const FILE_TYPES = ['md', 'txt', 'pdf', 'docx']

type ExternalRoot = {
  source_root_key: string
  path: string
  enabled: boolean
  sensitive: boolean
  source_kind: 'external_file'
}

// Root keys must be stable and machine-safe: lowercase letters, digits, hyphen, underscore.
const ROOT_KEY_PATTERN = /^[a-z0-9_-]+$/

function normalizeRoots(raw: any): ExternalRoot[] {
  if (!Array.isArray(raw)) return []
  return raw.map((r) => ({
    source_root_key: String(r?.source_root_key ?? ''),
    path: String(r?.path ?? ''),
    enabled: r?.enabled !== false,
    sensitive: !!r?.sensitive,
    source_kind: 'external_file' as const,
  }))
}

function normalizeExternalPath(path: string): string {
  const trimmed = path.trim()
  return trimmed.length > 1 ? trimmed.replace(/\/+$/, '') : trimmed
}

// Validate a single root's key + path. External source paths must be absolute; the backend
// expands a leading "~" to an absolute path, so both "/" and "~" prefixes are accepted here.
function validateRoot(root: { source_root_key: string; path: string }): string | null {
  const key = root.source_root_key.trim()
  const path = root.path.trim()
  if (!key) return 'Root key is required.'
  if (!ROOT_KEY_PATTERN.test(key)) {
    return `Root key "${key}" must use only lowercase letters, numbers, hyphen, or underscore (no spaces).`
  }
  if (!path) return 'Path is required.'
  if (!(path.startsWith('/') || path.startsWith('~'))) {
    return `Path "${path}" must be absolute (start with / or ~).`
  }
  return null
}

// Validate the full draft: per-row rules plus no duplicate keys / paths.
function validateRoots(roots: ExternalRoot[]): string | null {
  const seenKeys = new Set<string>()
  const seenPaths = new Set<string>()
  for (const root of roots) {
    const single = validateRoot(root)
    if (single) return single
    const key = root.source_root_key.trim()
    if (seenKeys.has(key)) return `Duplicate root key "${key}".`
    seenKeys.add(key)
    const path = normalizeExternalPath(root.path)
    if (seenPaths.has(path)) return `Duplicate path "${path}".`
    seenPaths.add(path)
  }
  return null
}

export function ObsidianMcpPanel() {
  const [config, setConfig] = useState<any>(null)
  const [status, setStatus] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [tools, setTools] = useState<any[]>([])
  const [grok, setGrok] = useState<any>(null)
  const [oauth, setOauth] = useState<any>(null)
  const [llmChat, setLlmChat] = useState<any>(null)
  const [chatgpt, setChatgpt] = useState<any>(null)
  const [chatgptReadiness, setChatgptReadiness] = useState<any>(null)
  const [mutations, setMutations] = useState<any[]>([])
  const [readReceipts, setReadReceipts] = useState<any[]>([])
  const [writeReadiness, setWriteReadiness] = useState<any>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<any>(null)
  const [tokenInput, setTokenInput] = useState('')
  const [listPath, setListPath] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [readPath, setReadPath] = useState('')
  const [sourceIndex, setSourceIndex] = useState<any>(null)
  const [watchStatus, setWatchStatus] = useState<any>(null)
  const [modelTest, setModelTest] = useState<any>(null)
  const [sourceIdInput, setSourceIdInput] = useState('')
  // External source roots editor (draft + Save roots). Draft is the config source of truth;
  // the watcher "Configured roots" list below reflects what the running watcher currently sees.
  const [draftRoots, setDraftRoots] = useState<ExternalRoot[]>([])
  const [rootsDirty, setRootsDirty] = useState(false)
  const [rootError, setRootError] = useState<string | null>(null)
  const [confirmRemoveIndex, setConfirmRemoveIndex] = useState<number | null>(null)
  const [newKey, setNewKey] = useState('')
  const [newPath, setNewPath] = useState('')
  const [newEnabled, setNewEnabled] = useState(true)
  const [newSensitive, setNewSensitive] = useState(false)
  const [rootsSavedWhileWatching, setRootsSavedWhileWatching] = useState(false)
  const [scanMaxFilesInput, setScanMaxFilesInput] = useState('')
  const [pollIntervalInput, setPollIntervalInput] = useState('')
  const [debounceInput, setDebounceInput] = useState('')
  const [cardMaxPerDrainInput, setCardMaxPerDrainInput] = useState('')
  const [excludedPartsInput, setExcludedPartsInput] = useState('')
  const [deferredPartsInput, setDeferredPartsInput] = useState('')

  async function refreshAll() {
    setBusy('refresh')
    setError(null)
    try {
      const [cfg, st, toolData, grokData, mutationData, oauthData, receiptData, chatgptData, llmChatData, sourceIdx, watchSt] =
        await Promise.all([
        getObsidianMcpConfig(),
        getObsidianMcpStatus(),
        getObsidianMcpTools(),
        getObsidianMcpGrokConfig(),
        getObsidianMcpMutations(10),
        getObsidianMcpOAuth(),
        getObsidianMcpReadReceipts(10),
        getObsidianMcpChatGPT(),
        getObsidianMcpLlmChatStatus(),
        getObsidianMcpSourceIndexStatus(),
        getObsidianMcpSourceWatchStatus(),
      ])
      setConfig((cfg as any).config || cfg)
      setStatus(st)
      setTools((toolData as any).tools || [])
      setGrok(grokData)
      setMutations((mutationData as any).mutations || [])
      setOauth(oauthData)
      setReadReceipts((receiptData as any).read_receipts || [])
      setChatgpt(chatgptData)
      setLlmChat(llmChatData)
      setSourceIndex(sourceIdx)
      setWatchStatus(watchSt)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAll()
  }, [])

  // Sync source-intelligence form state from the loaded config. The roots draft is only
  // re-seeded when there are no unsaved edits, so in-progress edits are never clobbered by a refresh.
  useEffect(() => {
    if (!config) return
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!rootsDirty) setDraftRoots(normalizeRoots(config.external_sources))
    setScanMaxFilesInput(config.external_source_scan_max_files != null ? String(config.external_source_scan_max_files) : '')
    setPollIntervalInput(config.watch_poll_interval_seconds != null ? String(config.watch_poll_interval_seconds) : '')
    setDebounceInput(config.watch_debounce_seconds != null ? String(config.watch_debounce_seconds) : '')
    setCardMaxPerDrainInput(config.source_card_auto_max_per_drain != null ? String(config.source_card_auto_max_per_drain) : '')
    setExcludedPartsInput(Array.isArray(config.source_index_excluded_path_parts) ? config.source_index_excluded_path_parts.join(', ') : '')
    setDeferredPartsInput(Array.isArray(config.source_index_deferred_path_parts) ? config.source_index_deferred_path_parts.join(', ') : '')
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [config, rootsDirty])

  async function saveConfig(patch: Record<string, unknown>): Promise<boolean> {
    setBusy('save')
    setError(null)
    setMessage(null)
    try {
      const payload = await patchObsidianMcpConfig(patch)
      setConfig((payload as any).config)
      setMessage('Obsidian MCP settings saved.')
      await refreshAll()
      return true
    } catch (err) {
      setError(err)
      return false
    } finally {
      setBusy(null)
    }
  }

  async function runSourceAction(key: string, fn: () => Promise<unknown>, okMessage: string) {
    setBusy(key)
    setError(null)
    setMessage(null)
    try {
      const result = await fn()
      if (key === 'model-test') setModelTest(result)
      if (key.startsWith('watch-')) {
        setWatchStatus(result)
        // Any watcher lifecycle action resolves the "roots changed, restart to apply" notice.
        setRootsSavedWhileWatching(false)
      }
      setMessage(okMessage)
      // Refresh the source-index + watcher snapshots after any mutating action.
      const [idx, watch] = await Promise.all([
        getObsidianMcpSourceIndexStatus(),
        getObsidianMcpSourceWatchStatus(),
      ])
      setSourceIndex(idx)
      if (!key.startsWith('watch-')) setWatchStatus(watch)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  function updateDraftRoot(index: number, patch: Partial<ExternalRoot>) {
    setDraftRoots(draftRoots.map((r, i) => (i === index ? { ...r, ...patch } : r)))
    setRootsDirty(true)
    setRootError(null)
  }

  function addDraftRoot() {
    const candidate = { source_root_key: newKey.trim(), path: newPath.trim() }
    const single = validateRoot(candidate)
    if (single) {
      setRootError(single)
      return
    }
    if (draftRoots.some((r) => r.source_root_key.trim() === candidate.source_root_key)) {
      setRootError(`Duplicate root key "${candidate.source_root_key}".`)
      return
    }
    const candPath = normalizeExternalPath(candidate.path)
    if (draftRoots.some((r) => normalizeExternalPath(r.path) === candPath)) {
      setRootError(`Duplicate path "${candPath}".`)
      return
    }
    setRootError(null)
    setDraftRoots([
      ...draftRoots,
      { ...candidate, enabled: newEnabled, sensitive: newSensitive, source_kind: 'external_file' },
    ])
    setRootsDirty(true)
    setNewKey('')
    setNewPath('')
    setNewEnabled(true)
    setNewSensitive(false)
  }

  function requestRemove(index: number) {
    setConfirmRemoveIndex(index)
  }

  function cancelRemove() {
    setConfirmRemoveIndex(null)
  }

  function confirmRemove(index: number) {
    setDraftRoots(draftRoots.filter((_, i) => i !== index))
    setRootsDirty(true)
    setConfirmRemoveIndex(null)
    setRootError(null)
  }

  function commitNumericField(field: string, raw: string, kind: 'int' | 'float') {
    const trimmed = raw.trim()
    if (trimmed === '') return
    const num = kind === 'int' ? Number.parseInt(trimmed, 10) : Number.parseFloat(trimmed)
    if (!Number.isFinite(num) || num <= 0) {
      setRootError(`Enter a positive number for ${field}.`)
      return
    }
    setRootError(null)
    void saveConfig({ [field]: num })
  }

  function commitExcludedParts() {
    const parts = excludedPartsInput.split(',').map((p) => p.trim()).filter((p) => p.length > 0)
    void saveConfig({ source_index_excluded_path_parts: parts })
  }

  function commitDeferredParts() {
    const parts = deferredPartsInput.split(',').map((p) => p.trim()).filter((p) => p.length > 0)
    void saveConfig({ source_index_deferred_path_parts: parts })
  }

  async function handleSaveRoots() {
    const err = validateRoots(draftRoots)
    if (err) {
      setRootError(err)
      return
    }
    setRootError(null)
    const payload = draftRoots.map((r) => ({
      source_root_key: r.source_root_key.trim(),
      path: r.path.trim(),
      enabled: r.enabled,
      sensitive: r.sensitive,
      source_kind: 'external_file' as const,
    }))
    const watching = !!watchStatus?.running
    const ok = await saveConfig({ external_sources: payload })
    if (ok) {
      setRootsDirty(false)
      if (watching) setRootsSavedWhileWatching(true)
    }
  }

  async function runLifecycle(action: 'enable' | 'disable' | 'restart') {
    setBusy(action)
    setError(null)
    setMessage(null)
    try {
      const result =
        action === 'enable'
          ? await enableObsidianMcp()
          : action === 'disable'
            ? await disableObsidianMcp()
            : await restartObsidianMcp()
      setStatus((result as any).status)
      setHealth((result as any).health)
      setConfig((result as any).config)
      setMessage(action === 'enable' ? 'MCP enabled.' : action === 'disable' ? 'MCP disabled.' : 'MCP restarted.')
      await refreshAll()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function runHealthCheck() {
    setBusy('health')
    setError(null)
    try {
      const result = await runObsidianMcpHealthCheck()
      setHealth(result)
      await refreshAll()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function runWriteReadiness() {
    setBusy('write-readiness')
    setError(null)
    try {
      const result = await runObsidianMcpWriteReadiness()
      setWriteReadiness(result)
      await refreshAll()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function runWriteSmoke() {
    setBusy('write-smoke')
    setError(null)
    setTestResult(null)
    try {
      const result = await testObsidianMcpWriteSmoke()
      setTestResult({ kind: 'write-smoke', result })
      await refreshAll()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function runChatgptReadiness() {
    setBusy('chatgpt-readiness')
    setError(null)
    try {
      const result = await runObsidianMcpChatGPTReadiness()
      setChatgptReadiness(result)
      await refreshAll()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function copyGrokConfig() {
    const text = JSON.stringify((grok as any)?.mcp_config || {}, null, 2)
    try {
      await navigator.clipboard.writeText(text)
      setMessage('Grok MCP config copied.')
    } catch {
      setMessage('Copy unavailable in this browser.')
    }
  }

  async function copyGrokOAuth() {
    const setup = (oauth as any)?.grok_setup
    if (!setup) {
      setMessage('Set a Public MCP Base URL to generate Grok OAuth values.')
      return
    }
    const text = [
      `MCP server URL:\n${setup.mcp_url}`,
      `Client ID:\n${setup.client_id}`,
      `Client Secret:\nleave blank`,
      `Authorization Endpoint:\n${setup.authorization_endpoint}`,
      `Token Endpoint:\n${setup.token_endpoint}`,
      `Scopes:\n${(setup.scopes || []).join('\n')}`,
      `Token Auth Method:\n${setup.token_auth_method}`,
    ].join('\n\n')
    try {
      await navigator.clipboard.writeText(text)
      setMessage('Grok OAuth setup values copied.')
    } catch {
      setMessage('Copy unavailable in this browser.')
    }
  }

  async function copyChatgptSetup() {
    const setup = (chatgpt as any)?.setup || (oauth as any)?.chatgpt_setup
    if (!setup) {
      setMessage('Set a Public MCP Base URL to generate ChatGPT setup values.')
      return
    }
    const text = [
      `Connector URL:\n${setup.connector_url}`,
      `Protected Resource Metadata:\n${setup.protected_resource_metadata_url}`,
      `Authorization Server Metadata:\n${setup.authorization_server_metadata_url}`,
      `Authorization Endpoint:\n${setup.authorization_endpoint}`,
      `Token Endpoint:\n${setup.token_endpoint}`,
      `Registration Endpoint:\n${setup.registration_endpoint}`,
      `Registration Mode:\n${setup.registration_mode}`,
      `Initial Scope:\n${setup.initial_scope}`,
      `CIMD Supported:\n${setup.client_id_metadata_document_supported ? 'yes' : 'no'}`,
    ].join('\n\n')
    try {
      await navigator.clipboard.writeText(text)
      setMessage('ChatGPT setup values copied.')
    } catch {
      setMessage('Copy unavailable in this browser.')
    }
  }

  async function runTest(kind: 'list' | 'search' | 'read') {
    setBusy(kind)
    setError(null)
    setTestResult(null)
    try {
      const result =
        kind === 'list'
          ? await testObsidianMcpListDirectory({ path: listPath, recursive: true })
          : kind === 'search'
            ? await testObsidianMcpSearch({ query: searchQuery, path_scope: config?.default_scope || undefined })
            : await testObsidianMcpReadFile({ path: readPath, max_chars: 1200 })
      setTestResult({ kind, result })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  const configText = useMemo(() => JSON.stringify((grok as any)?.mcp_config || {}, null, 2), [grok])
  const llmChatTools = useMemo(
    () => tools.filter((tool) => String(tool.name || '').startsWith('llm_chat_')),
    [tools],
  )
  const llmChatUsageExample = useMemo(
    () =>
      [
        '1. llm_chat_to_note_plan(transcript="...")',
        '2. Review plan_id, previews, and proposed_actions',
        '3. llm_chat_to_note_apply(plan_id="<plan_id>")',
      ].join('\n'),
    [],
  )

  async function copyText(text: string, successMessage: string) {
    try {
      await navigator.clipboard.writeText(text)
      setMessage(successMessage)
    } catch {
      setMessage('Copy unavailable in this browser.')
    }
  }
  const blockers = (health?.blocking_issues || status?.blocking_issues || []) as any[]
  const warnings = (health?.warnings || status?.warnings || []) as any[]
  const writePolicy = config || status?.write_policy || {}
  const chatgptInitialScopes = (chatgpt?.initial_scopes || config?.chatgpt_initial_scopes || ['obsidian.read']) as string[]
  const chatgptInitialScopeText = chatgpt?.setup?.initial_scope || chatgptInitialScopes.join(' ')
  const chatgptWriteEnabled = chatgptInitialScopes.includes('obsidian.write') || chatgptInitialScopeText.includes('obsidian.write')

  return (
    <SectionCard
      title="Obsidian MCP"
      description="Configure and monitor the local Grok-compatible Obsidian MCP service."
      actions={
        <button className="badge inline-flex items-center gap-1" onClick={refreshAll} disabled={busy !== null}>
          <RefreshCw size={13} aria-hidden />
          {busy === 'refresh' ? 'Refreshing...' : 'Refresh'}
        </button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-3">
          <div className="grid gap-2 text-xs sm:grid-cols-2">
            <StatusRow label="MCP" value={config?.enabled ? 'Enabled' : 'Disabled'} />
            <StatusRow label="Service" value={status?.service_state || 'Unknown'} />
            <StatusRow label="Mode" value={status?.mode || config?.mode || 'filesystem'} />
            <StatusRow label="Tools" value={String(status?.tools_registered ?? tools.length ?? 0)} />
            <StatusRow label="Token" value={config?.token_configured || status?.token_configured ? 'Configured' : 'Not configured'} />
            <StatusRow label="Last check" value={status?.last_health_check_at || health?.checked_at || 'Not run'} />
          </div>

          <div>
            <label htmlFor="obsidian-vault-root" className="text-xs mb-1">Vault root</label>
            <input
              id="obsidian-vault-root"
              className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
              value={config?.vault_root || ''}
              onChange={(event) => setConfig({ ...(config || {}), vault_root: event.target.value })}
              onBlur={() => saveConfig({ vault_root: config?.vault_root || '' })}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Host" value={config?.host || '127.0.0.1'} onChange={(value) => setConfig({ ...(config || {}), host: value })} onBlur={() => saveConfig({ host: config?.host })} />
            <Field label="Port" value={String(config?.port || 3010)} onChange={(value) => setConfig({ ...(config || {}), port: Number(value) })} onBlur={() => saveConfig({ port: Number(config?.port || 3010) })} />
            <Field label="Max file MB" value={String(config?.max_file_mb || 100)} onChange={(value) => setConfig({ ...(config || {}), max_file_mb: Number(value) })} onBlur={() => saveConfig({ max_file_mb: Number(config?.max_file_mb || 100) })} />
            <Field label="Max result chars" value={String(config?.max_result_chars || 12000)} onChange={(value) => setConfig({ ...(config || {}), max_result_chars: Number(value) })} onBlur={() => saveConfig({ max_result_chars: Number(config?.max_result_chars || 12000) })} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="obsidian-default-scope" className="text-xs mb-1">Default scope</label>
              <input
                id="obsidian-default-scope"
                className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
                value={config?.default_scope || ''}
                onChange={(event) => setConfig({ ...(config || {}), default_scope: event.target.value })}
                onBlur={() => saveConfig({ default_scope: config?.default_scope || '' })}
                placeholder="Projects"
              />
            </div>
            <div>
              <label htmlFor="obsidian-token" className="text-xs mb-1">Bearer token</label>
              <div className="flex gap-2">
                <input
                  id="obsidian-token"
                  className="min-w-0 flex-1 rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
                  type="password"
                  value={tokenInput}
                  onChange={(event) => setTokenInput(event.target.value)}
                  placeholder={config?.token_configured ? 'Configured' : 'Paste local token'}
                />
                <button
                  className="badge"
                  onClick={() => {
                    saveConfig({ bearer_token: tokenInput })
                    setTokenInput('')
                  }}
                  disabled={busy !== null || !tokenInput.trim()}
                >
                  Save
                </button>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {FILE_TYPES.map((type) => {
              const enabled = (config?.allowed_file_types || FILE_TYPES).includes(type)
              return (
                <button
                  key={type}
                  className={`badge ${enabled ? 'badge-fresh' : 'badge-muted'}`}
                  onClick={() => {
                    const current = new Set(config?.allowed_file_types || FILE_TYPES)
                    if (current.has(type)) current.delete(type)
                    else current.add(type)
                    const next = Array.from(current)
                    setConfig({ ...(config || {}), allowed_file_types: next })
                    saveConfig({ allowed_file_types: next })
                  }}
                  disabled={busy !== null}
                >
                  .{type}
                </button>
              )
            })}
          </div>

          <div className="rounded border border-[var(--hb-border)] p-3">
            <div className="text-sm font-medium">Autonomous Vault Manager</div>
            <p className="mt-1 text-xs text-[var(--hb-muted)]">
              Write mode grants durable authority to authenticated MCP clients for policy-governed Markdown note creation and replacement.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <Toggle
                label="Write mode"
                checked={Boolean(writePolicy.writes_enabled)}
                onChange={(checked) => saveConfig({ writes_enabled: checked })}
                disabled={busy !== null}
              />
              <Toggle
                label="Markdown management"
                checked={Boolean(writePolicy.vault_markdown_write_enabled)}
                onChange={(checked) => saveConfig({ vault_markdown_write_enabled: checked })}
                disabled={busy !== null}
              />
              <Toggle
                label="Create parent folders"
                checked={writePolicy.create_parent_dirs_enabled !== false}
                onChange={(checked) => saveConfig({ create_parent_dirs_enabled: checked })}
                disabled={busy !== null}
              />
              <Toggle
                label="Backup before replace"
                checked={writePolicy.backup_before_replace !== false}
                onChange={(checked) => saveConfig({ backup_before_replace: checked })}
                disabled={busy !== null}
              />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field
                label="Max write chars"
                value={String(writePolicy.max_write_chars || 120000)}
                onChange={(value) => setConfig({ ...(config || {}), max_write_chars: Number(value) })}
                onBlur={() => saveConfig({ max_write_chars: Number(config?.max_write_chars || 120000) })}
              />
              <StatusRow label="Protected paths" value={(writePolicy.protected_paths || []).join(', ') || 'Default'} />
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button className="badge inline-flex items-center gap-1" onClick={runHealthCheck} disabled={busy !== null}>
              <ShieldCheck size={13} aria-hidden />
              {busy === 'health' ? 'Checking...' : 'Run Health Check'}
            </button>
            <button className="badge" onClick={() => runLifecycle('enable')} disabled={busy !== null}>Enable MCP</button>
            <button className="badge" onClick={() => runLifecycle('disable')} disabled={busy !== null}>Disable MCP</button>
            <button className="badge" onClick={() => runLifecycle('restart')} disabled={busy !== null}>Restart MCP service</button>
            <button className="badge" onClick={runWriteReadiness} disabled={busy !== null}>{busy === 'write-readiness' ? 'Checking...' : 'Run write readiness'}</button>
            <button className="badge" onClick={runWriteSmoke} disabled={busy !== null}>{busy === 'write-smoke' ? 'Writing...' : 'Run write smoke test'}</button>
          </div>

          <IssueList title="Blocking issues" items={blockers} empty="No blocking issues reported." />
          <IssueList title="Warnings" items={warnings} empty="No warnings reported." />

          <div className="rounded border border-[var(--hb-border)] p-3">
            <div className="mb-2 text-sm font-medium">Write readiness</div>
            <div className="grid gap-2 text-xs sm:grid-cols-2">
              <StatusRow label="Write mode" value={writePolicy.writes_enabled ? 'Enabled' : 'Disabled'} />
              <StatusRow label="Markdown writes" value={writePolicy.vault_markdown_write_enabled ? 'Enabled' : 'Disabled'} />
              <StatusRow label="Vault writable" value={writeReadiness?.vault_writable === false ? 'No' : writeReadiness ? 'Yes' : 'Not checked'} />
              <StatusRow label="Backup writable" value={writeReadiness?.backup_writable === false ? 'No' : writeReadiness ? 'Yes' : 'Not checked'} />
            </div>
          </div>

          <div className="rounded border border-[var(--hb-border)] p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="text-sm font-medium">Grok Remote MCP config</div>
              <button className="badge inline-flex items-center gap-1" onClick={copyGrokConfig}>
                <Copy size={13} aria-hidden />
                Copy Grok MCP config
              </button>
            </div>
            <pre className="max-h-40 overflow-auto rounded bg-black/20 p-2 text-[11px]">{configText}</pre>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded border border-[var(--hb-border)] p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-medium">Remote Connector / OAuth</h4>
          <button className="badge inline-flex items-center gap-1" onClick={copyGrokOAuth}>
            <Copy size={13} aria-hidden />
            Copy Grok OAuth setup values
          </button>
        </div>
        <p className="text-xs text-[var(--hb-muted)]">
          OAuth 2.1 Authorization Code with PKCE lets the Grok Custom Connector reach the tunneled MCP endpoint. Scopes never bypass the vault write policy.
        </p>
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
          <StatusRow label="OAuth" value={oauth?.oauth_enabled ? 'Enabled' : 'Disabled'} />
          <StatusRow label="Token auth method" value={oauth?.token_auth_method || 'none (PKCE)'} />
          <StatusRow label="Client ID" value={oauth?.client_id || 'hb-obsidian-grok'} />
          <StatusRow label="Scopes" value={(oauth?.scopes_supported || ['obsidian.read', 'obsidian.write']).join(', ')} />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Toggle
            label="OAuth enabled"
            checked={Boolean(oauth?.oauth_enabled ?? config?.oauth_enabled)}
            onChange={(checked) => saveConfig({ oauth_enabled: checked })}
            disabled={busy !== null}
          />
          <div>
            <label htmlFor="obsidian-public-base-url" className="text-xs mb-1">Public MCP Base URL</label>
            <input
              id="obsidian-public-base-url"
              className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
              value={config?.public_base_url || ''}
              onChange={(event) => setConfig({ ...(config || {}), public_base_url: event.target.value })}
              onBlur={() => saveConfig({ public_base_url: config?.public_base_url || '' })}
              placeholder="https://mcp.bobby-fetting.me"
            />
          </div>
        </div>
        <div className="mt-3 grid gap-2 text-xs">
          <StatusRow label="MCP URL" value={oauth?.endpoints?.mcp_url || 'Set the Public MCP Base URL'} />
          <StatusRow label="Authorization endpoint" value={oauth?.endpoints?.authorization_endpoint || 'Set the Public MCP Base URL'} />
          <StatusRow label="Token endpoint" value={oauth?.endpoints?.token_endpoint || 'Set the Public MCP Base URL'} />
        </div>
        <div className="mt-3">
          <div className="text-xs font-medium">Recent OAuth events</div>
          {(oauth?.recent_events || []).length === 0 ? (
            <div className="mt-1 text-xs text-[var(--hb-muted)]">No OAuth events recorded.</div>
          ) : (
            <div className="mt-2 grid gap-2">
              {(oauth?.recent_events || []).map((event: any, index: number) => (
                <div key={`${event.at || 'oauth-event'}-${index}`} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge badge-muted">{event.kind || 'event'}</span>
                    {event.scope ? <span className="text-[var(--hb-muted)]">{event.scope}</span> : null}
                    <span className="text-[10px] text-[var(--hb-muted)]">{event.at || ''}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 rounded border border-[var(--hb-border)] p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-medium">LLM Chat Memory Tools</h4>
          <button className="badge" onClick={() => copyText(llmChatUsageExample, 'LLM chat usage example copied.')} type="button">
            <Copy className="mr-1 inline h-3 w-3" /> Copy usage example
          </button>
        </div>
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
          <StatusRow label="Enabled" value={llmChat?.llm_chat_enabled ? 'Yes' : 'No'} />
          <StatusRow label="Plan store count" value={String(llmChat?.plan_count ?? 0)} />
          <StatusRow label="Template directory" value={llmChat?.template_dir || config?.llm_chat_template_dir || 'Templates/LLM Chat'} />
          <StatusRow label="Project template" value={llmChat?.project_template_path || config?.llm_chat_project_template_path || 'Templates/Template - Project Note.md'} />
          <StatusRow label="Raw transcript persistence" value={llmChat?.raw_transcript_persistence ? 'On' : 'Off'} />
          <StatusRow label="Redaction" value={llmChat?.redaction_enabled ? 'On' : 'Off'} />
        </div>
        <div className="mt-3">
          <div className="text-xs font-medium">Tools ({llmChatTools.length})</div>
          <div className="mt-2 grid gap-2">
            {llmChatTools.map((tool) => (
              <div key={tool.name} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{tool.name}</span>
                  <span className="badge badge-muted">{tool.scope || 'obsidian.read'}</span>
                </div>
                <div className="mt-1 text-[var(--hb-muted)]">{tool.description}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-3">
          <div className="text-xs font-medium">Recent plans</div>
          {(llmChat?.recent_plans || []).length === 0 ? (
            <div className="mt-1 text-xs text-[var(--hb-muted)]">No LLM chat plans recorded yet.</div>
          ) : (
            <div className="mt-2 grid gap-2">
              {(llmChat?.recent_plans || []).map((plan: any, index: number) => (
                <div key={`${plan.plan_id || 'plan'}-${index}`} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono">{plan.plan_id}</span>
                    <span className="badge badge-muted">{plan.primary_domain || plan.plan_kind}</span>
                    <span className="text-[var(--hb-muted)]">{plan.created_at || ''}</span>
                    <span className="text-[var(--hb-muted)]">{plan.action_count ?? 0} action(s)</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <TechnicalDetails summary="LLM chat usage example" details={llmChatUsageExample} className="mt-3" />
      </div>

      <div className="mt-4 rounded border border-[var(--hb-border)] p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-medium">ChatGPT App Connection</h4>
          <div className="flex flex-wrap gap-2">
            <button className="badge inline-flex items-center gap-1" onClick={copyChatgptSetup}>
              <Copy size={13} aria-hidden />
              Copy ChatGPT setup values
            </button>
            <button className="badge inline-flex items-center gap-1" onClick={runChatgptReadiness} disabled={busy !== null}>
              <Play size={13} aria-hidden />
              {busy === 'chatgpt-readiness' ? 'Checking...' : 'Run readiness check'}
            </button>
          </div>
        </div>
        <div className="grid gap-2 text-xs sm:grid-cols-2">
          <StatusRow label="ChatGPT" value={chatgpt?.enabled ? 'Enabled' : 'Disabled'} />
          <StatusRow label="Profile" value={chatgptWriteEnabled ? 'Write-enabled OAuth' : 'Read-only OAuth'} />
          <StatusRow label="DCR" value={chatgpt?.dynamic_client_registration_enabled ? 'Enabled' : 'Disabled'} />
          <StatusRow label="CIMD" value={chatgpt?.client_id_metadata_document_supported ? 'Advertised' : 'Disabled'} />
          <StatusRow label="Initial scopes" value={chatgptInitialScopeText} />
          <StatusRow label="Readiness" value={chatgptReadiness ? (chatgptReadiness.ok ? 'Passing' : 'Needs attention') : 'Not checked'} />
        </div>
        <div className="mt-3 grid gap-2 text-xs">
          <Toggle
            label="ChatGPT write-enabled OAuth"
            checked={chatgptWriteEnabled}
            onChange={(checked) =>
              saveConfig({
                chatgpt_readonly_mode: !checked,
                chatgpt_initial_scopes: checked ? ['obsidian.read', 'obsidian.write'] : ['obsidian.read'],
              })
            }
            disabled={busy !== null}
          />
          {chatgptWriteEnabled ? (
            <div className="rounded border border-amber-400/60 bg-amber-500/10 p-2 text-amber-100">
              Write-enabled ChatGPT OAuth tokens can invoke write-capable MCP tools, but writes remain constrained by the configured vault write policy and protected-path rules. Recreate or reconnect the ChatGPT connector with Advanced OAuth scope: obsidian.read obsidian.write.
            </div>
          ) : (
            <div className="text-[var(--hb-muted)]">Read-only profile uses Advanced OAuth scope: obsidian.read.</div>
          )}
        </div>
        <div className="mt-3 grid gap-2 text-xs">
          <StatusRow label="Connector URL" value={chatgpt?.setup?.connector_url || oauth?.chatgpt_setup?.connector_url || 'Set the Public MCP Base URL'} />
          <StatusRow label="Protected resource metadata" value={chatgpt?.setup?.protected_resource_metadata_url || oauth?.endpoints?.protected_resource_metadata_endpoint || 'Set the Public MCP Base URL'} />
          <StatusRow label="Authorization metadata" value={chatgpt?.setup?.authorization_server_metadata_url || oauth?.endpoints?.metadata_endpoint || 'Set the Public MCP Base URL'} />
          <StatusRow label="Registration endpoint" value={chatgpt?.setup?.registration_endpoint || oauth?.endpoints?.registration_endpoint || 'Set the Public MCP Base URL'} />
        </div>
        {chatgptReadiness?.checks?.length ? (
          <div className="mt-3 grid gap-2">
            {chatgptReadiness.checks.map((check: any) => (
              <div key={check.name} className="flex flex-wrap items-center gap-2 rounded border border-[var(--hb-border)] p-2 text-xs">
                <span className={`badge ${check.status === 'pass' ? 'badge-fresh' : 'badge-stale'}`}>{check.status}</span>
                <span className="font-medium">{check.name}</span>
                <span className="text-[var(--hb-muted)]">{check.detail}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-[var(--hb-border)] p-3">
          <h4 className="text-sm font-medium">Tool Registry ({tools.length})</h4>
          <div className="mt-2 space-y-3">
            {groupToolsByCategory(tools).map(([category, list]) => (
              <div key={category}>
                <div className="text-[10px] font-semibold uppercase tracking-wide text-[var(--hb-muted)]">
                  {category} ({list.length})
                </div>
                <div className="mt-1 space-y-2">
                  {list.map((tool) => (
                    <div key={tool.name} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">{tool.name}</span>
                        <span className="flex items-center gap-1">
                          {isHighRiskTool(tool.name) && <span className="badge badge-stale">High-risk write</span>}
                          <span className={`badge ${tool.enabled ? 'badge-fresh' : 'badge-stale'}`}>{tool.enabled ? 'Enabled' : 'Disabled'}</span>
                        </span>
                      </div>
                      <div className="mt-1 text-[var(--hb-muted)]">{tool.description}</div>
                      <div className="mt-1 font-mono text-[10px]">{tool.input_schema_summary}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded border border-[var(--hb-border)] p-3">
          <h4 className="text-sm font-medium">Test tools</h4>
          <div className="mt-3 grid gap-3">
            <TestRow label="Directory path" value={listPath} onChange={setListPath} button="Run test directory listing" onClick={() => runTest('list')} busy={busy === 'list'} />
            <TestRow label="Search query" value={searchQuery} onChange={setSearchQuery} button="Run test search" onClick={() => runTest('search')} busy={busy === 'search'} />
            <TestRow label="File path" value={readPath} onChange={setReadPath} button="Run test file read" onClick={() => runTest('read')} busy={busy === 'read'} />
          </div>
          <TechnicalDetails summary="Latest test result" details={testResult ? JSON.stringify(testResult, null, 2) : undefined} className="mt-3" />
        </div>
      </div>

      <div className="mt-4 rounded border border-[var(--hb-border)] p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-medium">Recent mutation events</h4>
          <button className="badge" onClick={refreshAll} disabled={busy !== null}>Refresh events</button>
        </div>
        {mutations.length === 0 ? (
          <div className="mt-2 text-xs text-[var(--hb-muted)]">No mutation events recorded.</div>
        ) : (
          <div className="mt-2 grid gap-2">
            {mutations.map((event, index) => (
              <div key={`${event.timestamp || 'event'}-${index}`} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`badge ${event.status === 'applied' ? 'badge-fresh' : 'badge-stale'}`}>{event.status || 'unknown'}</span>
                  <span className="font-medium">{event.action || 'mutation'}</span>
                  <span className="text-[var(--hb-muted)]">{event.relative_path || 'path unavailable'}</span>
                </div>
                <div className="mt-1 grid gap-1 text-[10px] text-[var(--hb-muted)] sm:grid-cols-3">
                  <span>{event.timestamp || 'no timestamp'}</span>
                  <span>{event.error_code || 'ok'}</span>
                  <span>{event.backup_path ? 'backup recorded' : 'no backup'}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 rounded border border-[var(--hb-border)] p-3">
        <h4 className="text-sm font-medium">Read / crawl receipts</h4>
        {readReceipts.length === 0 ? (
          <div className="mt-2 text-xs text-[var(--hb-muted)]">No bulk read receipts recorded.</div>
        ) : (
          <div className="mt-2 grid gap-2">
            {readReceipts.map((receipt, index) => (
              <div key={`${receipt.timestamp || 'read'}-${index}`} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="badge badge-fresh">read</span>
                  <span className="font-medium">{receipt.tool_name || 'crawl'}</span>
                  <span className="text-[var(--hb-muted)]">{receipt.scope || 'scope unavailable'}</span>
                </div>
                <div className="mt-1 grid gap-1 text-[10px] text-[var(--hb-muted)] sm:grid-cols-3">
                  <span>{receipt.timestamp || 'no timestamp'}</span>
                  <span>{receipt.file_count != null ? `${receipt.file_count} files` : '—'}</span>
                  <span>{receipt.principal_kind || 'principal n/a'}{receipt.truncated ? ' · truncated' : ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-[var(--hb-border)] p-3 text-xs">
          <h4 className="text-sm font-medium">Read hardening &amp; search</h4>
          <p className="mt-2 text-[var(--hb-muted)]">
            OAuth clients cannot list, search, or read hidden/system/protected paths. Semantic search
            falls back to lexical with a warning until a local-first vector index is configured.
          </p>
          <div className="mt-2">
            <div className="text-[10px] uppercase text-[var(--hb-muted)]">Protected paths</div>
            <div className="mt-1 flex flex-wrap gap-1">
              {(config?.protected_paths || []).map((path: string) => (
                <span key={path} className="badge badge-stale font-mono">{path}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded border border-[var(--hb-border)] p-3 text-xs">
          <h4 className="text-sm font-medium">Grok usage examples</h4>
          <p className="mt-2 text-[var(--hb-muted)]">Copyable arguments for common second-brain tools.</p>
          {GROK_EXAMPLES.map((example) => (
            <div key={example.tool} className="mt-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px]">{example.tool}</span>
                <button className="badge inline-flex items-center gap-1" onClick={() => copyText(example.args, `${example.tool} arguments copied.`)}>
                  <Copy size={12} aria-hidden /> Copy
                </button>
              </div>
              <pre className="mt-1 overflow-x-auto rounded bg-[var(--hb-bg)] p-2 font-mono text-[10px]">{example.args}</pre>
            </div>
          ))}
        </div>
      </div>

        <div className="rounded border border-[var(--hb-border)] p-3 text-xs">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-medium">Source Intelligence</h4>
            <button className="badge inline-flex items-center gap-1" onClick={() => runSourceAction('rebuild', rebuildObsidianMcpSourceIndex, 'Source index rebuild queued.')} disabled={busy !== null}>
              <RefreshCw size={12} aria-hidden /> {busy === 'rebuild' ? 'Queuing...' : 'Rebuild index'}
            </button>
          </div>

          <div className="mb-2 text-[10px] text-[var(--hb-muted)]">
            Rebuild re-indexes changed files and{' '}
            {config?.source_card_auto_generate_enabled
              ? 'generates deterministic source cards'
              : 'does not generate cards (deterministic cards are off)'}
            {config?.source_summary_auto_generate_enabled
              ? ' plus bounded advisory summaries (model permitting)'
              : '; advisory summaries are off, but deterministic cards may still be generated'}
            . Cards are written to <span className="font-mono">Source Notes/&lt;source path&gt;.md</span>.
          </div>

          {(sourceIndex?.config_warnings || []).length > 0 && (
            <div className="mb-2 rounded border border-amber-400 bg-amber-50 p-2 text-amber-700">
              {(sourceIndex.config_warnings as string[]).map((w) => (
                <div key={w} className="font-mono text-[10px]">{w}</div>
              ))}
            </div>
          )}

          <div className="grid gap-2 sm:grid-cols-3">
            <StatusRow label="Indexed sources" value={String(sourceIndex?.sources_total ?? '—')} />
            <StatusRow label="Queued / processing / error" value={`${sourceIndex?.queued_count ?? 0} / ${sourceIndex?.processing_count ?? 0} / ${sourceIndex?.error_count ?? 0}`} />
            <StatusRow label="Stale notes" value={String(sourceIndex?.stale_note_count ?? 0)} />
            <StatusRow label="Summaries (stale)" value={`${sourceIndex?.summarized_count ?? 0} (${sourceIndex?.stale_summary_count ?? 0})`} />
            <StatusRow label="Generated cards" value={String(sourceIndex?.generated_card_count ?? 0)} />
            <StatusRow label="Last generation (cards/sum)" value={sourceIndex?.last_generation_at ? `${sourceIndex?.last_generation_cards ?? 0} / ${sourceIndex?.last_generation_summaries ?? 0}` : '—'} />
            <StatusRow label="Last indexed" value={sourceIndex?.last_indexed_at || 'Never'} />
            <StatusRow label="FTS available" value={sourceIndex?.fts_available ? 'Yes' : 'No'} />
          </div>

          <div className="mt-3 rounded border border-[var(--hb-border)] p-2">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium">External source roots</span>
              <button className="badge inline-flex items-center gap-1" onClick={handleSaveRoots} disabled={busy !== null || !rootsDirty}>
                {busy === 'save' ? 'Saving...' : 'Save roots'}{rootsDirty ? ' *' : ''}
              </button>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              <Toggle label="External source indexing enabled" checked={!!config?.external_source_index_enabled} onChange={(v) => saveConfig({ external_source_index_enabled: v })} disabled={busy !== null} />
              <Toggle label="External source watcher enabled" checked={!!config?.external_source_watch_enabled} onChange={(v) => saveConfig({ external_source_watch_enabled: v })} disabled={busy !== null} />
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <Field label="Scan max files" value={scanMaxFilesInput} onChange={setScanMaxFilesInput} onBlur={() => commitNumericField('external_source_scan_max_files', scanMaxFilesInput, 'int')} />
              <Field label="Watch poll interval (s)" value={pollIntervalInput} onChange={setPollIntervalInput} onBlur={() => commitNumericField('watch_poll_interval_seconds', pollIntervalInput, 'int')} />
              <Field label="Watch debounce (s)" value={debounceInput} onChange={setDebounceInput} onBlur={() => commitNumericField('watch_debounce_seconds', debounceInput, 'float')} />
            </div>

            {rootError && (
              <div className="mt-2 rounded border border-amber-400 bg-amber-50 p-2 text-amber-700" role="alert">{rootError}</div>
            )}

            <div className="mt-2 space-y-2">
              {draftRoots.length === 0 ? (
                <div className="text-[var(--hb-muted)]">No external source roots configured.</div>
              ) : (
                draftRoots.map((root, idx) => (
                  <div key={idx} className="rounded border border-[var(--hb-border)] p-2">
                    <div className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
                      <input className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={root.source_root_key} onChange={(e) => updateDraftRoot(idx, { source_root_key: e.target.value })} placeholder="root key" aria-label={`root key ${idx}`} />
                      <input className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={root.path} onChange={(e) => updateDraftRoot(idx, { path: e.target.value })} placeholder="/absolute/path" aria-label={`root path ${idx}`} />
                      <span className="badge badge-muted self-center" title="Source kind is fixed for external roots">external_file</span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <label className="flex items-center gap-1 text-xs">
                        <input type="checkbox" checked={root.enabled} onChange={(e) => updateDraftRoot(idx, { enabled: e.target.checked })} aria-label={`root enabled ${idx}`} />
                        enabled
                      </label>
                      <label className="flex items-center gap-1 text-xs">
                        <input type="checkbox" checked={root.sensitive} onChange={(e) => updateDraftRoot(idx, { sensitive: e.target.checked })} aria-label={`root sensitive ${idx}`} />
                        sensitive
                      </label>
                      {confirmRemoveIndex === idx ? (
                        <>
                          <button className="badge badge-stale" onClick={() => confirmRemove(idx)} disabled={busy !== null}>Confirm remove</button>
                          <button className="badge" onClick={cancelRemove} disabled={busy !== null}>Cancel</button>
                        </>
                      ) : (
                        <button className="badge" onClick={() => requestRemove(idx)} disabled={busy !== null}>Remove</button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="mt-3 rounded border border-dashed border-[var(--hb-border)] p-2">
              <div className="text-[10px] uppercase text-[var(--hb-muted)]">Add external root</div>
              <div className="mt-1 grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
                <input className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="root key" aria-label="new root key" />
                <input className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={newPath} onChange={(e) => setNewPath(e.target.value)} placeholder="/absolute/path" aria-label="new root path" />
                <button className="badge" onClick={addDraftRoot} disabled={busy !== null}>Add</button>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-1 text-xs">
                  <input type="checkbox" checked={newEnabled} onChange={(e) => setNewEnabled(e.target.checked)} aria-label="new root enabled" />
                  enabled
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <input type="checkbox" checked={newSensitive} onChange={(e) => setNewSensitive(e.target.checked)} aria-label="new root sensitive" />
                  sensitive
                </label>
                <span className="badge badge-muted">external_file</span>
              </div>
            </div>

            {rootsSavedWhileWatching && watchStatus?.running && (
              <div className="mt-2 rounded border border-amber-400 bg-amber-50 p-2 text-amber-700" role="alert">
                Roots saved. The watcher is running with the previous roots — click <span className="font-medium">Restart</span> (below) to apply the saved roots.
              </div>
            )}
          </div>

          <div className="mt-3 rounded border border-[var(--hb-border)] p-2">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">Watcher</span>
              <span className={`badge ${watchStatus?.running ? 'badge-fresh' : 'badge-muted'}`}>{watchStatus?.running ? `running (${watchStatus?.mode})` : 'stopped'}</span>
              <button className="badge" onClick={() => runSourceAction('watch-start', startObsidianMcpSourceWatch, 'Watcher started.')} disabled={busy !== null}>Start</button>
              <button className="badge" onClick={() => runSourceAction('watch-stop', stopObsidianMcpSourceWatch, 'Watcher stopped.')} disabled={busy !== null}>Stop</button>
              <button className="badge" onClick={() => runSourceAction('watch-restart', restartObsidianMcpSourceWatch, 'Watcher restarted.')} disabled={busy !== null}>Restart</button>
              <button className="badge" onClick={() => runSourceAction('watch-test', testObsidianMcpSourceWatchEvent, 'Test event drained.')} disabled={busy !== null}>Test event</button>
              <button className="badge" onClick={() => runSourceAction('watch-recover', recoverObsidianMcpSourceWatchStuck, 'Stuck events recovered.')} disabled={busy !== null}>Recover stuck</button>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <StatusRow label="Oldest processing (s)" value={String(watchStatus?.queue_health?.oldest_processing_age_seconds ?? '—')} />
              <StatusRow label="Last drain" value={watchStatus?.queue_health?.last_drain_at || 'Never'} />
              <StatusRow label="Last note / summary" value={`${watchStatus?.queue_health?.last_note_at ? 'Y' : '—'} / ${watchStatus?.queue_health?.last_summary_at ? 'Y' : '—'}`} />
            </div>
            <div className="mt-2">
              <div className="text-[10px] uppercase text-[var(--hb-muted)]">Configured roots</div>
              {(watchStatus?.roots || sourceIndex?.watcher?.roots || []).length === 0 ? (
                <div className="mt-1 text-[var(--hb-muted)]">No external source roots configured.</div>
              ) : (
                <ul className="mt-1 space-y-1">
                  {(watchStatus?.roots || []).map((root: any) => (
                    <li key={root.key} className="flex items-center gap-2">
                      <span className={`badge ${root.enabled ? 'badge-fresh' : 'badge-muted'}`}>{root.enabled ? 'on' : 'off'}</span>
                      {root.sensitive && <span className="badge badge-stale">sensitive</span>}
                      <span className="font-mono text-[10px]">{root.key}</span>
                      <span className="truncate text-[var(--hb-muted)]">{root.path}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="mt-3 rounded border border-[var(--hb-border)] p-2">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">Summary model</span>
              <button className="badge" onClick={() => runSourceAction('model-test', testObsidianMcpModel, 'Model test complete.')} disabled={busy !== null}>{busy === 'model-test' ? 'Testing...' : 'Test model'}</button>
            </div>
            {modelTest ? (
              <div className="grid gap-2 sm:grid-cols-3">
                <StatusRow label="Requested" value={modelTest.requested || '—'} />
                <StatusRow label="Resolved" value={modelTest.resolved || '—'} />
                <StatusRow label="Match" value={modelTest.match || '—'} />
                <StatusRow label="Available" value={modelTest.available ? 'Yes' : 'No'} />
                <StatusRow label="Latency (ms)" value={String(modelTest.latency_ms ?? '—')} />
                <StatusRow label="Installed" value={String((modelTest.models || []).length)} />
              </div>
            ) : (
              <div className="text-[var(--hb-muted)]">Run a model test to validate the configured summary model against installed Ollama tags.</div>
            )}
            {modelTest?.match === 'missing' && (
              <div className="mt-2 rounded border border-amber-400 bg-amber-50 p-2 text-amber-700">Configured model not installed. Pick one of: {(modelTest.models || []).join(', ') || '(none)'}.</div>
            )}
            {modelTest?.match === 'tag_resolved' && (
              <div className="mt-2 text-[var(--hb-muted)]">Bare tag resolves to <span className="font-mono">{modelTest.resolved}</span>. Consider pinning it in config.</div>
            )}
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <Toggle label="Auto-generate cards on index" checked={!!config?.source_card_auto_generate_enabled} onChange={(v) => saveConfig({ source_card_auto_generate_enabled: v })} disabled={busy !== null} />
            <Toggle label="Auto-summarize on index" checked={!!config?.source_summary_auto_generate_enabled} onChange={(v) => saveConfig({ source_summary_auto_generate_enabled: v })} disabled={busy !== null} />
            <Toggle label="Auto-refresh existing cards" checked={config?.source_note_auto_refresh_enabled !== false} onChange={(v) => saveConfig({ source_note_auto_refresh_enabled: v })} disabled={busy !== null} />
          </div>

          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <Field label="Card auto max per drain" value={cardMaxPerDrainInput} onChange={setCardMaxPerDrainInput} onBlur={() => commitNumericField('source_card_auto_max_per_drain', cardMaxPerDrainInput, 'int')} />
          </div>

          <div className="mt-3">
            <Field label="Excluded path parts" value={excludedPartsInput} onChange={setExcludedPartsInput} onBlur={commitExcludedParts} />
            <div className="mt-1 rounded border border-amber-400 bg-amber-50 p-2 text-[10px] text-amber-700" role="note">
              Comma-separated path segments (e.g. <span className="font-mono">node_modules, .venv, dist, build</span>). Broad roots can create
              low-value cards unless excluded paths are set; excluded paths are skipped during indexing and card generation.
            </div>
          </div>

          <div className="mt-3">
            <Field label="Deferred path parts" value={deferredPartsInput} onChange={setDeferredPartsInput} onBlur={commitDeferredParts} />
            <div className="mt-1 text-[10px] text-[var(--hb-muted)]" role="note">
              Comma-separated path segments (e.g. <span className="font-mono">HB INSURANCE RENEWALS</span>). Deferred sources are still indexed
              and searchable, but are intentionally not auto-carded or auto-summarized (distinct from hard exclusions).
            </div>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto]">
            <input className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={sourceIdInput} onChange={(e) => setSourceIdInput(e.target.value)} placeholder="source_id" aria-label="source id" />
            <button className="badge" onClick={() => runSourceAction('gen-card', () => generateObsidianMcpSourceCard({ source_id: sourceIdInput, overwrite: true }), 'Source card generated.')} disabled={busy !== null || !sourceIdInput.trim()}>Generate card</button>
            <button className="badge" onClick={() => runSourceAction('summarize', () => summarizeObsidianMcpSource({ source_id: sourceIdInput }), 'Summarize requested.')} disabled={busy !== null || !sourceIdInput.trim()}>Summarize</button>
          </div>
          <div className="mt-2">
            <button className="badge" onClick={() => runSourceAction('refresh-stale', () => refreshObsidianMcpStaleSourceNotes({ max_updates: 25 }), 'Stale source notes refreshed.')} disabled={busy !== null}>Refresh stale notes</button>
          </div>
        </div>

      {message && <div className="mt-3 text-xs text-green-600">{message}</div>}
      <ErrorState userMessage="Obsidian MCP settings could not be loaded." error={error} className="mt-3" />
    </SectionCard>
  )
}

const HIGH_RISK_TOOLS = new Set([
  'vault_move_note_apply',
  'vault_rename_note_apply',
  'vault_archive_note_apply',
  'vault_update_frontmatter',
  'vault_curation_apply',
  'vault_email_to_note_apply',
])

function isHighRiskTool(name: string): boolean {
  return HIGH_RISK_TOOLS.has(name)
}

function groupToolsByCategory(tools: any[]): [string, any[]][] {
  const groups = new Map<string, any[]>()
  for (const tool of tools) {
    const category = tool.category || 'Other'
    if (!groups.has(category)) groups.set(category, [])
    groups.get(category)!.push(tool)
  }
  return Array.from(groups.entries())
}

const GROK_EXAMPLES = [
  { tool: 'vault_map', args: JSON.stringify({ root_path: 'Work', recursive: true, max_depth: 2, max_files: 100 }, null, 2) },
  { tool: 'vault_email_inventory', args: JSON.stringify({ root_path: 'Work/Email/inbox', max_files: 25, include_body_preview: false }, null, 2) },
  { tool: 'vault_curation_plan', args: JSON.stringify({ root_path: 'Work/HB Personal Assistant', strategy: 'second_brain', dry_run: true }, null, 2) },
]

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--hb-border)] p-2">
      <div className="text-[10px] uppercase text-[var(--hb-muted)]">{label}</div>
      <div className="mt-1 truncate font-medium">{value}</div>
    </div>
  )
}

function Field({ label, value, onChange, onBlur }: { label: string; value: string; onChange: (value: string) => void; onBlur: () => void }) {
  const id = `obsidian-${label.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <div>
      <label htmlFor={id} className="text-xs mb-1">{label}</label>
      <input id={id} className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={value} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} />
    </div>
  )
}

function Toggle({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (checked: boolean) => void; disabled: boolean }) {
  const id = `obsidian-toggle-${label.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <label htmlFor={id} className="flex items-center justify-between gap-3 rounded border border-[var(--hb-border)] p-2 text-xs">
      <span>{label}</span>
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} disabled={disabled} />
    </label>
  )
}

function IssueList({ title, items, empty }: { title: string; items: any[]; empty: string }) {
  return (
    <div className="rounded border border-[var(--hb-border)] p-3 text-xs">
      <div className="font-medium">{title}</div>
      {items.length === 0 ? (
        <div className="mt-1 text-[var(--hb-muted)]">{empty}</div>
      ) : (
        <ul className="mt-2 space-y-1">
          {items.map((item, index) => (
            <li key={`${item.code || item.name || title}-${index}`}>
              <span className="badge badge-stale mr-2">{item.code || item.name || 'issue'}</span>
              <span className="text-[var(--hb-muted)]">{item.detail || item.message || 'Review required.'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TestRow({ label, value, onChange, button, onClick, busy }: { label: string; value: string; onChange: (value: string) => void; button: string; onClick: () => void; busy: boolean }) {
  const id = `obsidian-test-${label.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
      <div>
        <label htmlFor={id} className="text-xs mb-1">{label}</label>
        <input id={id} className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm" value={value} onChange={(event) => onChange(event.target.value)} />
      </div>
      <button className="badge self-end inline-flex items-center gap-1" onClick={onClick} disabled={busy}>
        <Play size={13} aria-hidden />
        {busy ? 'Running...' : button}
      </button>
    </div>
  )
}
