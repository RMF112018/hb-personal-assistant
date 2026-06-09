/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react'
import {
  startProcoreSourceAuth,
  getProcoreSourceAuthStatus,
  refreshProcoreSourceAuth,
  type ProcoreAuthStartResult,
  type AuthFlowStatus,
} from '../../lib/api'
import { ErrorState } from '../common/ErrorState'
import { TechnicalDetails } from '../common/TechnicalDetails'
import { getSourceStateCopy } from '../../lib/statusCopy'
import { safeDisplayText } from '../../lib/errorCopy'

export function ProcoreSourceCard({
  status,
  onComplete,
  compact = false,
  freshness,
}: {
  status?: any
  onComplete?: () => void
  compact?: boolean
  freshness?: string | null
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [startResult, setStartResult] = useState<ProcoreAuthStartResult | null>(null)
  const [pollStatus, setPollStatus] = useState<AuthFlowStatus | null>(null)
  const [manualCode, setManualCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const pollTimer = useRef<number | null>(null)
  const mounted = useRef(true)

  const state = (status?.status || status?.state || 'never_connected') as string
  const copy = getSourceStateCopy(state)
  const isConnected = state === 'connected_valid' || state === 'connected_refreshing'

  const missingConfig = !!(status?.missing_config)
  const missingMapping = !!(status?.missing_mapping)
  const pendingProjects: string[] = Array.isArray(status?.pending_projects) ? status.pending_projects : (status?.mapping?.pending_projects || [])
  const needsReauth = state.includes('reauth') || status?.needs_reauth

  function clearPoll() {
    if (pollTimer.current) {
      window.clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      clearPoll()
    }
  }, [])

  async function handleStart() {
    setBusy('start')
    setError(null)
    setStartResult(null)
    setPollStatus(null)
    clearPoll()
    try {
      const res = await startProcoreSourceAuth()
      setStartResult(res)
      const flowId = res.flow_id
      pollTimer.current = window.setInterval(async () => {
        try {
          const s = await getProcoreSourceAuthStatus(flowId)
          if (!mounted.current) return
          setPollStatus(s)
          if (s.status === 'complete' || s.status === 'expired' || s.status === 'failed') {
            clearPoll()
            if (s.status === 'complete') onComplete?.()
          }
        } catch {
          if (!mounted.current) return
        }
      }, 4000)
    } catch (e: any) {
      setError(safeDisplayText(e))
    } finally {
      setBusy(null)
    }
  }

  function openAuthUrl() {
    if (startResult?.authorization_url) {
      window.open(startResult.authorization_url, '_blank', 'noopener')
    }
  }

  async function handleManualExchange() {
    if (!manualCode.trim()) return
    setBusy('exchange')
    setError(null)
    try {
      // For source bridge the exchange may be handled by status poll or a dedicated; call refresh as safe fallback after manual.
      await refreshProcoreSourceAuth()
      setManualCode('')
      onComplete?.()
    } catch (e: any) {
      setError(safeDisplayText(e))
    } finally {
      setBusy(null)
    }
  }

  async function handleRefreshAuth() {
    setBusy('refresh')
    setError(null)
    try {
      await refreshProcoreSourceAuth()
      onComplete?.()
    } catch (e: any) {
      setError(safeDisplayText(e))
    } finally {
      setBusy(null)
    }
  }

  const showFlow = !!startResult && (!pollStatus || pollStatus.status === 'pending')
  const showManual = !!startResult && (startResult.manual_code_fallback_available || startResult.callback_mode === 'oob')

  const mode = status?.mode || status?.live_mode || 'local'

  return (
    <div className={compact ? 'text-xs' : ''}>
      <div className="font-medium mb-1 flex items-center gap-2">
        Procore (Source)
        <span className={`badge ${copy.tone === 'success' ? 'badge-fresh' : copy.tone === 'danger' ? 'badge-stale' : ''}`}>{copy.label}</span>
      </div>

      {freshness && (
        <div className="text-[10px] text-[var(--hb-muted)] mb-1">Last local update: {freshness}</div>
      )}
      <div className="text-[10px] text-[var(--hb-muted)] mb-2">Mode: {mode}</div>

      {missingConfig && (
        <div className="text-xs mb-1 text-amber-400">Not configured</div>
      )}
      {missingMapping && (
        <div className="text-xs mb-1 text-amber-400">Pending project mapping{pendingProjects.length ? `: ${pendingProjects.slice(0,3).join(', ')}` : ''}</div>
      )}
      {needsReauth && (
        <div className="text-xs mb-1 text-red-400">Reauth required</div>
      )}

      {isConnected ? (
        <div className="text-xs mb-2">
          Connected.
          <button className="badge ml-2" onClick={handleRefreshAuth} disabled={!!busy}>
            {busy === 'refresh' ? 'Refreshing…' : 'Refresh auth'}
          </button>
        </div>
      ) : (
        <button className="badge" onClick={handleStart} disabled={!!busy || !!showFlow}>
          {busy === 'start' ? 'Starting…' : 'Connect'}
        </button>
      )}

      <ErrorState message={error} onRetry={handleStart} />

      {showFlow && startResult && (
        <div className="mt-2 card text-xs">
          <div className="font-medium mb-1">Authorize in Procore</div>
          <button className="badge" onClick={openAuthUrl}>Open Procore to authorize</button>
          <div className="text-[10px] text-[var(--hb-muted)] mt-2">A new tab/window will open. Complete authorization there. This page will update automatically when the callback finishes. Connecting does not start sync.</div>

          {showManual && (
            <div className="mt-3 border-t border-[var(--hb-border)] pt-2">
              <div className="text-[10px] mb-1">Manual code fallback (if the browser flow cannot complete):</div>
              <div className="flex gap-2">
                <input className="border bg-[var(--hb-bg)] px-2 py-1 text-xs flex-1" placeholder="Paste authorization code" value={manualCode} onChange={(e) => setManualCode(e.target.value)} aria-label="Procore authorization code for manual exchange" />
                <button className="badge" onClick={handleManualExchange} disabled={!!busy || !manualCode.trim()}>
                  {busy === 'exchange' ? 'Exchanging…' : 'Exchange code'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {pollStatus && (
        <div className="mt-1 text-xs">
          {pollStatus.status === 'pending' && 'Waiting for Procore authorization to complete…'}
          {pollStatus.status === 'complete' && 'Procore source connected.'}
          {pollStatus.status === 'expired' && 'Authorization window expired. Start again.'}
          {pollStatus.status === 'failed' && 'Authorization failed. You can try again.'}
        </div>
      )}

      <TechnicalDetails summary="Advanced source details" details={status ? safeDetail(status) : undefined} className="mt-2" />

      <div className="text-[10px] text-[var(--hb-muted)] mt-1">Backend-controlled OAuth for sources. No tokens or secrets shown.</div>
    </div>
  )
}

function safeDetail(v: any) {
  if (!v) return ''
  if (typeof v !== 'object') return String(v)
  return Object.keys(v).filter(k => !/token|secret|key|password/i.test(k)).map(k => `${k}: ${safeDisplayText(v[k])}`).join('\n')
}
