/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react'
import {
  startGraphSourceAuth,
  getGraphSourceAuthStatus,
  refreshGraphSourceAuth,
  type GraphAuthStartResult,
  type AuthFlowStatus,
} from '../../lib/api'
import { ErrorState } from '../common/ErrorState'
import { TechnicalDetails } from '../common/TechnicalDetails'
import { getSourceStateCopy } from '../../lib/statusCopy'
import { safeDisplayText } from '../../lib/errorCopy'

export function GraphSourceCard({
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
  const [startResult, setStartResult] = useState<GraphAuthStartResult | null>(null)
  const [pollStatus, setPollStatus] = useState<AuthFlowStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollTimer = useRef<number | null>(null)
  const mounted = useRef(true)

  const state = (status?.status || status?.state || 'never_connected') as string
  const copy = getSourceStateCopy(state)
  const isConnected = state === 'connected_valid' || state === 'connected_refreshing'

  const scopeMissing = !!(status?.scope_presence?.missing || status?.missing_scope)
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
      const res = await startGraphSourceAuth()
      setStartResult(res)
      const flowId = res.flow_id
      pollTimer.current = window.setInterval(async () => {
        try {
          const s = await getGraphSourceAuthStatus(flowId)
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

  async function handleRefreshAuth() {
    setBusy('refresh')
    setError(null)
    try {
      await refreshGraphSourceAuth()
      onComplete?.()
    } catch (e: any) {
      setError(safeDisplayText(e))
    } finally {
      setBusy(null)
    }
  }

  function copyToClipboard(text: string) {
    try { navigator.clipboard.writeText(text) } catch { /* clipboard may be unavailable */ }
  }

  const showFlow = !!startResult && (!pollStatus || pollStatus.status === 'pending')

  const mode = status?.mode || status?.live_mode || 'local'

  return (
    <div className={compact ? 'text-xs' : ''}>
      <div className="font-medium mb-1 flex items-center gap-2">
        Microsoft 365 (Source)
        <span className={`badge ${copy.tone === 'success' ? 'badge-fresh' : copy.tone === 'danger' ? 'badge-stale' : ''}`}>{copy.label}</span>
      </div>

      {freshness && (
        <div className="text-[10px] text-[var(--hb-muted)] mb-1">Last local update: {freshness}</div>
      )}
      <div className="text-[10px] text-[var(--hb-muted)] mb-2">Mode: {mode}</div>

      {scopeMissing && (
        <div className="text-xs mb-1 text-amber-400">Missing scope (needs re-consent)</div>
      )}
      {needsReauth && (
        <div className="text-xs mb-1 text-red-400">Reauth required</div>
      )}

      {isConnected ? (
        <div className="text-xs mb-2">
          Connected{status?.account_hint ? ` • ${safeDisplayText(status.account_hint)}` : ''}.
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
          <div className="font-medium mb-1">Complete sign-in in your browser</div>
          <div className="mb-1">Enter this code at the Microsoft sign-in page:</div>
          <div className="font-mono text-base tracking-[3px] bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-3 py-2 select-all">
            {startResult.user_code}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="badge" onClick={() => copyToClipboard(startResult.user_code)}>Copy code</button>
            <a className="badge underline" href={startResult.verification_uri_complete || startResult.verification_uri} target="_blank" rel="noreferrer">Open sign-in page</a>
          </div>
          <div className="text-[10px] text-[var(--hb-muted)] mt-2">Connecting does not start sync. No tokens are shown.</div>
        </div>
      )}

      {pollStatus && (
        <div className="mt-1 text-xs">
          {pollStatus.status === 'pending' && 'Waiting for sign-in to complete…'}
          {pollStatus.status === 'complete' && 'Microsoft 365 source connected.'}
          {pollStatus.status === 'expired' && 'Sign-in window expired. Start again.'}
          {pollStatus.status === 'failed' && 'Sign-in failed. You can try again.'}
        </div>
      )}

      <TechnicalDetails summary="Advanced source details" details={status ? safeDetail(status) : undefined} className="mt-2" />

      <div className="text-[10px] text-[var(--hb-muted)] mt-1">Uses source auth bridge. No tokens or secrets are stored or shown.</div>
    </div>
  )
}

function safeDetail(v: any) {
  if (!v) return ''
  if (typeof v !== 'object') return String(v)
  return Object.keys(v).filter(k => !/token|secret|key|password/i.test(k)).map(k => `${k}: ${safeDisplayText(v[k])}`).join('\n')
}
