/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  getEnvironment,
  getSourcesStatus,
  getSchedulerStatus,
  refreshSourcesDryRun,
  refreshSourcesLocal,
  refreshSourcesLive,
} from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { LoadingState } from '../common/LoadingState'
import { ErrorState } from '../common/ErrorState'
import { safeDisplayText } from '../../lib/errorCopy'
import { formatLastUpdate } from '../../lib/timeAgo'
import { GraphSourceCard } from './GraphSourceCard'
import { ProcoreSourceCard } from './ProcoreSourceCard'

export function SourceConnectionsPanel() {
  const { data: env, isFetching: envFetching, error: envError, refetch: refetchEnv } = useQuery({
    queryKey: ['environment'],
    queryFn: getEnvironment,
    staleTime: 15_000,
  })
  const { data: sources, isFetching: srcFetching, error: srcError, refetch: refetchSrc } = useQuery({
    queryKey: ['sources', 'status'],
    queryFn: getSourcesStatus,
    staleTime: 15_000,
  })
  const { data: sched, isFetching: schFetching, error: schError, refetch: refetchSch } = useQuery({
    queryKey: ['scheduler', 'status'],
    queryFn: getSchedulerStatus,
    staleTime: 15_000,
  })

  const [busy, setBusy] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<any>(null)

  const isFetching = envFetching || srcFetching || schFetching
  const loadError = envError || srcError || schError

  const sourceRefreshMode = (sources as any)?.source_refresh_mode || (env as any)?.source_refresh_mode || 'unknown'
  const live = (sources as any)?.live_refresh || (env as any)?.live_refresh || {}
  const liveEnabled = !!live.enabled
  const liveReason = live.reason || (live.available === false ? 'unavailable in this environment' : undefined)

  const lastUpdate = (sched as any)?.last_successful_schedule_date || (sources as any)?.scheduler?.last_successful_schedule_date

  async function runRefresh(kind: 'dry' | 'local' | 'live') {
    setBusy(kind)
    setReceipt(null)
    try {
      let res: any
      if (kind === 'dry') {
        res = await refreshSourcesDryRun()
      } else if (kind === 'local') {
        res = await refreshSourcesLocal()
      } else {
        if (!window.confirm('Live external reads will be attempted (Graph/Procore). Continue?')) {
          setBusy(null)
          return
        }
        res = await refreshSourcesLive(true)
      }
      setReceipt(res)
      // refresh status after action
      await Promise.all([refetchEnv(), refetchSrc(), refetchSch()])
    } catch (e: any) {
      setReceipt({ status: 'error', message: safeDisplayText(e) })
    } finally {
      setBusy(null)
    }
  }

  async function handleAuthComplete() {
    await refetchSrc()
  }

  const modeLabel = sourceRefreshMode === 'mock_data' ? 'Dev / mock data' : sourceRefreshMode === 'local_or_gated_live' ? 'Production (gated live)' : sourceRefreshMode

  return (
    <SectionCard
      title="Source Connections"
      description="Local source status, last update, and safe refresh controls. Live refresh is confirmation-gated and disabled when the environment or config does not allow external reads."
      actions={
        <button className="badge" onClick={() => { refetchEnv(); refetchSrc(); refetchSch() }} disabled={isFetching}>
          {isFetching ? 'Checking…' : 'Refresh status'}
        </button>
      }
    >
      <div className="text-xs mb-2">
        <span className="badge">{modeLabel}</span>
        {liveReason && <span className="ml-2 text-[var(--hb-muted)]">Live refresh: {liveReason}</span>}
        {!liveEnabled && !liveReason && <span className="ml-2 text-[var(--hb-muted)]">Live refresh disabled</span>}
      </div>

      <div className="text-xs text-[var(--hb-muted)] mb-3">{formatLastUpdate(lastUpdate)}</div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="border border-[var(--hb-border)] rounded p-3">
          <GraphSourceCard
            status={(sources as any)?.graph}
            onComplete={handleAuthComplete}
            compact
          />
        </div>
        <div className="border border-[var(--hb-border)] rounded p-3">
          <ProcoreSourceCard
            status={(sources as any)?.procore}
            onComplete={handleAuthComplete}
            compact
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button className="badge" onClick={() => runRefresh('dry')} disabled={!!busy}>
          {busy === 'dry' ? 'Running dry-run…' : 'Dry-run refresh'}
        </button>
        <button className="badge" onClick={() => runRefresh('local')} disabled={!!busy}>
          {busy === 'local' ? 'Running local refresh…' : 'Local refresh'}
        </button>
        <button className="badge" onClick={() => runRefresh('live')} disabled={!!busy || !liveEnabled}>
          {busy === 'live' ? 'Running live refresh…' : 'Live refresh'}
        </button>
      </div>

      {receipt && (
        <div className="mt-2 text-xs">
          Receipt: {safeDisplayText((receipt as any)?.status || (receipt as any)?.kind, 'ok')} { (receipt as any)?.live_mode ? `• ${(receipt as any).live_mode}` : '' }
        </div>
      )}

      <LoadingState label="Loading source status…" className={isFetching && !sources ? '' : 'hidden'} />

      <ErrorState error={loadError} userMessage="Source connections status could not be loaded." onRetry={() => { refetchEnv(); refetchSrc(); refetchSch() }} />

      <div className="text-[10px] text-[var(--hb-muted)] mt-2">
        Dry-run and local refresh are always safe. Live refresh performs external reads and is disabled or confirmation-gated depending on environment and scheduler policy.
      </div>
    </SectionCard>
  )
}
