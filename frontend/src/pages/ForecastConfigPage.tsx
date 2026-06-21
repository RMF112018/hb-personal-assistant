/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — configuration viewer (Implementation Phase 2, read-only).
 * Shows the current immutable config snapshot that drives forecasts: controls, model controls,
 * staffing mappings, owner-SOV crosswalk, and project settings. Business settings only — no
 * paths, run stamps, endpoints, or internals (the backend redacts them structurally). */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

function cell(value: any): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return String(value)
  return String(value)
}

export function ForecastConfigPage() {
  const { data: snapsResp, isLoading, error } = useQuery({
    queryKey: ['forecast', 'config', 'snapshots'],
    queryFn: () => api.getForecastConfigSnapshots(),
  })

  const snapshots: any[] = Array.isArray(snapsResp?.snapshots) ? snapsResp.snapshots : []
  const snapshotId: string | undefined = snapshots[0]?.snapshot_id

  const { data: snapResp } = useQuery({
    queryKey: ['forecast', 'config', 'snapshot', snapshotId],
    queryFn: () => api.getForecastConfigSnapshot(snapshotId as string),
    enabled: Boolean(snapshotId),
  })

  const domains: any[] = Array.isArray(snapResp?.domains) ? snapResp.domains : []
  const [domain, setDomain] = useState<string | undefined>(undefined)
  useEffect(() => {
    if (!domain && domains.length > 0) setDomain(domains[0].domain)
  }, [domains, domain])

  const { data: domainResp } = useQuery({
    queryKey: ['forecast', 'config', 'domain', snapshotId, domain],
    queryFn: () => api.getForecastConfigDomain(snapshotId as string, domain as string),
    enabled: Boolean(snapshotId && domain),
  })

  const items: any[] = Array.isArray(domainResp?.items) ? domainResp.items : []
  const columns = useMemo(() => {
    if (items.length === 0) return [] as string[]
    return Object.keys(items[0].fields || {}).slice(0, 8)
  }, [items])

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading forecast configuration…</div>
  }

  if (error) {
    const status = (error as any)?.status
    const message =
      status === 503
        ? 'Forecast configuration is not available in this environment yet.'
        : 'We could not load forecast configuration right now.'
    return (
      <div className="card">
        <div className="text-xs mb-2">
          <Link to="/forecasting" className="underline">
            ← Back to forecast packages
          </Link>
        </div>
        <EmptyState title="Configuration unavailable" hint={message} />
      </div>
    )
  }

  const snap = snapResp || snapshots[0] || {}

  return (
    <div>
      <div className="text-xs mb-2">
        <Link to="/forecasting" className="underline">
          ← Back to forecast packages
        </Link>
      </div>

      <div className="card">
        <div className="flex items-center justify-between gap-3">
          <div className="section-title">Forecast configuration</div>
          <Link to="/forecasting/config/proposals" className="text-sm underline">
            Propose / view edits
          </Link>
        </div>
        <p className="text-sm text-[var(--hb-muted)]">
          {snap.snapshot_name ? `${snap.snapshot_name}` : 'Current configuration'}
          {snap.created_display ? ` · Captured ${snap.created_display}` : ''}
          {snap.item_count ? ` · ${snap.item_count} settings` : ''}
        </p>
        {domains.length === 0 ? (
          <EmptyState title="No configuration found" hint="The current config snapshot has no settings." />
        ) : (
          <div className="flex flex-wrap gap-2 mt-3">
            {domains.map((d: any) => {
              const active = d.domain === domain
              return (
                <button
                  key={d.domain}
                  type="button"
                  onClick={() => setDomain(d.domain)}
                  className={`rounded border px-3 py-2 text-sm text-left ${
                    active ? 'border-[var(--hb-accent)]' : 'border-[var(--hb-border)]'
                  }`}
                >
                  <div className="font-medium">{d.display_label}</div>
                  <div className="text-xs text-[var(--hb-muted)]">{d.item_count} items</div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {domain && (
        <div className="card mt-3">
          <div className="section-title">{domainResp?.display_label || 'Settings'}</div>
          {domain === 'forecast_controls' && (
            <p className="text-xs text-amber-300 mb-2">
              Deprecated — superseded by Model controls. Shown read-only; not editable.
            </p>
          )}
          {items.length === 0 ? (
            <EmptyState title="No items" hint="This configuration area has no items." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                    {columns.map((c) => (
                      <th key={c} className="py-2 pr-3">
                        {c.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.slice(0, 500).map((it: any) => (
                    <tr key={it.item_id} className="border-b border-[var(--hb-border)] align-top">
                      {columns.map((c) => (
                        <td key={c} className="py-2 pr-3">
                          {cell((it.fields || {})[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {(domainResp?.truncated || items.length > 500) && (
                <p className="text-xs text-[var(--hb-muted)] mt-2">
                  Showing the first {Math.min(items.length, 500)} items.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
