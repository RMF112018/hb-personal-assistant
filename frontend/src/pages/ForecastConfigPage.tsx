/* Forecast configuration viewer — read-only business settings (Phase 2). */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastActionLink,
  ForecastBackLink,
  ForecastDomainTile,
  ForecastPageHeader,
  ForecastShell,
  ForecastSubnav,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPageChrome'
import { useEffectiveSelection } from '../components/forecast/useEffectiveSelection'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

function cell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return '—'
  return String(value)
}

type ConfigDomain = { domain: string; display_label?: string; item_count?: number }
type ConfigItem = { item_id: string; fields?: Record<string, unknown> }

export function ForecastConfigPage() {
  const { data: snapsResp, isLoading, error } = useQuery({
    queryKey: ['forecast', 'config', 'snapshots'],
    queryFn: () => api.getForecastConfigSnapshots(),
  })

  const snapshots = Array.isArray(snapsResp?.snapshots) ? snapsResp.snapshots : []
  const snapshotId = snapshots[0]?.snapshot_id as string | undefined

  const { data: snapResp } = useQuery({
    queryKey: ['forecast', 'config', 'snapshot', snapshotId],
    queryFn: () => api.getForecastConfigSnapshot(snapshotId as string),
    enabled: Boolean(snapshotId),
  })

  const domains = useMemo(
    () => (Array.isArray(snapResp?.domains) ? snapResp.domains : []) as ConfigDomain[],
    [snapResp],
  )
  const domainOptions = useMemo(() => domains.map((d) => d.domain), [domains])
  const [domain, setDomain] = useEffectiveSelection(domainOptions)

  const { data: domainResp } = useQuery({
    queryKey: ['forecast', 'config', 'domain', snapshotId, domain],
    queryFn: () => api.getForecastConfigDomain(snapshotId as string, domain as string),
    enabled: Boolean(snapshotId && domain),
  })

  const items = useMemo(
    () => (Array.isArray(domainResp?.items) ? domainResp.items : []) as ConfigItem[],
    [domainResp],
  )
  const columns = useMemo(() => {
    if (items.length === 0) return [] as string[]
    return Object.keys(items[0].fields || {}).slice(0, 8)
  }, [items])

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading forecast configuration…</div>
  }

  if (error) {
    const status = (error as { status?: number })?.status
    const isUnconfigured = status === 503
    return (
      <div>
        <ForecastBackLink />
        <ForecastSubnav />
        <div className="card">
          <EmptyState
            title="Configuration unavailable"
            hint={
              isUnconfigured
                ? 'No forecast configuration snapshot is available yet. Check storage and database readiness.'
                : 'We could not load forecast configuration right now.'
            }
            actions={
              isUnconfigured ? (
                <ForecastActionLink to="/forecasting/runtime" variant="primary">
                  Open storage settings
                </ForecastActionLink>
              ) : undefined
            }
          />
        </div>
      </div>
    )
  }

  const snap = snapResp || snapshots[0] || {}

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Forecast configuration"
          subtitle="Read-only view of the configuration snapshot that drives forecasts — project settings, model controls, staffing, and crosswalks."
          actions={
            <ForecastActionLink to="/forecasting/config/proposals">Config proposals</ForecastActionLink>
          }
        />
        <p className="text-sm text-[var(--hb-muted)] mt-2">
          {(snap.snapshot_name as string) || 'Current snapshot'}
          {snap.created_display ? ` · Captured ${snap.created_display}` : ''}
          {snap.item_count ? ` · ${snap.item_count} settings` : ''}
        </p>

        {domains.length === 0 ? (
          <EmptyState
            title="No configuration found"
            hint="The current snapshot has no settings. Generate or import data after storage is ready."
          />
        ) : (
          <div className="flex flex-wrap gap-2 mt-4">
            {domains.map((d) => (
              <ForecastDomainTile
                key={d.domain}
                label={d.display_label || d.domain}
                count={d.item_count}
                active={d.domain === domain}
                onClick={() => setDomain(d.domain)}
              />
            ))}
          </div>
        )}
      </section>

      {domain && (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">{(domainResp?.display_label as string) || 'Settings'}</h2>
          {domain === 'forecast_controls' && (
            <p className="text-xs text-amber-300 mb-2">
              Legacy controls — superseded by Model controls. Shown read-only.
            </p>
          )}
          {items.length === 0 ? (
            <EmptyState title="No items" hint="This configuration area has no items." />
          ) : (
            <>
              <ForecastTable
                headers={
                  <>
                    {columns.map((c) => (
                      <ForecastTh key={c} className="capitalize">
                        {c.replace(/_/g, ' ')}
                      </ForecastTh>
                    ))}
                  </>
                }
              >
                {items.slice(0, 500).map((it) => (
                  <tr key={it.item_id} className="align-top">
                    {columns.map((c) => (
                      <ForecastTd key={c}>{cell((it.fields || {})[c])}</ForecastTd>
                    ))}
                  </tr>
                ))}
              </ForecastTable>
              {(domainResp?.truncated || items.length > 500) && (
                <p className="text-xs text-[var(--hb-muted)] mt-2">
                  Showing the first {Math.min(items.length, 500)} items.
                </p>
              )}
            </>
          )}
        </section>
      )}
    </ForecastShell>
  )
}