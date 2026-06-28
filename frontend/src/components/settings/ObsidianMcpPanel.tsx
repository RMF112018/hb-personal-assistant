/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from 'react'
import { Copy, Play, RefreshCw, ShieldCheck } from 'lucide-react'

import {
  disableObsidianMcp,
  enableObsidianMcp,
  getObsidianMcpConfig,
  getObsidianMcpGrokConfig,
  getObsidianMcpStatus,
  getObsidianMcpTools,
  patchObsidianMcpConfig,
  restartObsidianMcp,
  runObsidianMcpHealthCheck,
  testObsidianMcpListDirectory,
  testObsidianMcpReadFile,
  testObsidianMcpSearch,
} from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { ErrorState } from '../common/ErrorState'
import { TechnicalDetails } from '../common/TechnicalDetails'

const FILE_TYPES = ['md', 'txt', 'pdf', 'docx']

export function ObsidianMcpPanel() {
  const [config, setConfig] = useState<any>(null)
  const [status, setStatus] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [tools, setTools] = useState<any[]>([])
  const [grok, setGrok] = useState<any>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<any>(null)
  const [tokenInput, setTokenInput] = useState('')
  const [listPath, setListPath] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [readPath, setReadPath] = useState('')

  async function refreshAll() {
    setBusy('refresh')
    setError(null)
    try {
      const [cfg, st, toolData, grokData] = await Promise.all([
        getObsidianMcpConfig(),
        getObsidianMcpStatus(),
        getObsidianMcpTools(),
        getObsidianMcpGrokConfig(),
      ])
      setConfig((cfg as any).config || cfg)
      setStatus(st)
      setTools((toolData as any).tools || [])
      setGrok(grokData)
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

  async function saveConfig(patch: Record<string, unknown>) {
    setBusy('save')
    setError(null)
    setMessage(null)
    try {
      const payload = await patchObsidianMcpConfig(patch)
      setConfig((payload as any).config)
      setMessage('Obsidian MCP settings saved.')
      await refreshAll()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
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

  async function copyGrokConfig() {
    const text = JSON.stringify((grok as any)?.mcp_config || {}, null, 2)
    try {
      await navigator.clipboard.writeText(text)
      setMessage('Grok MCP config copied.')
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
  const blockers = (health?.blocking_issues || status?.blocking_issues || []) as any[]
  const warnings = (health?.warnings || status?.warnings || []) as any[]

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
          </div>

          <IssueList title="Blocking issues" items={blockers} empty="No blocking issues reported." />
          <IssueList title="Warnings" items={warnings} empty="No warnings reported." />

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

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-[var(--hb-border)] p-3">
          <h4 className="text-sm font-medium">Tool Registry</h4>
          <div className="mt-2 space-y-2">
            {tools.map((tool) => (
              <div key={tool.name} className="rounded border border-[var(--hb-border)] p-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{tool.name}</span>
                  <span className={`badge ${tool.enabled ? 'badge-fresh' : 'badge-stale'}`}>{tool.enabled ? 'Enabled' : 'Disabled'}</span>
                </div>
                <div className="mt-1 text-[var(--hb-muted)]">{tool.description}</div>
                <div className="mt-1 font-mono text-[10px]">{tool.input_schema_summary}</div>
                <div className="mt-1 text-[var(--hb-muted)]">Last validation: {tool.last_validation_status}</div>
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

      {message && <div className="mt-3 text-xs text-green-600">{message}</div>}
      <ErrorState userMessage="Obsidian MCP settings could not be loaded." error={error} className="mt-3" />
    </SectionCard>
  )
}

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
