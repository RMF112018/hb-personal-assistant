/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — Run Center (Implementation Phase 3).
 * Lets an operator generate a deterministic context→analysis forecast and lists prior runs.
 * Generation writes only to an isolated work area; it never changes the live data or the live
 * database. Business labels only — no paths, run stamps, or internals are shown. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { StatusPill } from './ForecastingPage'
import { api } from '../lib/api'

export function ForecastRunCenterPage() {
  const { data: runsResp, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'runs'],
    queryFn: () => api.getForecastRuns(),
  })

  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)

  const { data: detailResp } = useQuery({
    queryKey: ['forecast', 'run', selectedId],
    queryFn: () => api.getForecastRun(selectedId as string),
    enabled: Boolean(selectedId),
  })

  async function onGenerate() {
    setGenerating(true)
    setGenError(null)
    try {
      await api.startForecastRun()
      await refetch()
    } catch (e: any) {
      const status = e?.status
      setGenError(
        status === 503
          ? 'Forecast generation is not configured in this environment yet.'
          : 'The forecast generation could not be started.',
      )
    } finally {
      setGenerating(false)
    }
  }

  const runs: any[] = Array.isArray(runsResp?.runs) ? runsResp.runs : []
  const detail = detailResp || null

  return (
    <div>
      <div className="text-xs mb-2">
        <Link to="/forecasting" className="underline">
          ← Back to forecast packages
        </Link>
      </div>

      <div className="card">
        <div className="flex items-center justify-between gap-3">
          <div className="section-title">Run a forecast</div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {generating ? 'Generating…' : 'Generate forecast'}
          </button>
        </div>
        <p className="text-sm text-[var(--hb-muted)]">
          Generates a deterministic context → analysis forecast into an isolated work area. The live
          project data and database are never changed.
        </p>
        {genError && <p className="text-sm text-rose-300 mt-2">{genError}</p>}
      </div>

      <div className="card mt-3">
        <div className="section-title">Run history</div>
        {isLoading ? (
          <div className="text-sm text-[var(--hb-muted)]">Loading runs…</div>
        ) : error ? (
          <EmptyState title="Runs unavailable" hint="We could not load the run history right now." />
        ) : runs.length === 0 ? (
          <EmptyState title="No runs yet" hint="Generate a forecast to see it here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Run</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Generated</th>
                  <th className="py-2 pr-3"></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r: any) => (
                  <tr key={r.run_id} className="border-b border-[var(--hb-border)]">
                    <td className="py-2 pr-3">{r.display_label}</td>
                    <td className="py-2 pr-3">
                      <StatusPill status={r.status === 'succeeded' ? 'validated' : 'attention'} />
                    </td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">{r.generated_display || '—'}</td>
                    <td className="py-2 pr-3">
                      <button type="button" onClick={() => setSelectedId(r.run_id)} className="underline">
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {detail && (
        <div className="card mt-3">
          <div className="section-title">{detail.display_label || 'Run detail'}</div>
          <p className="text-sm">
            Status: <span className="font-medium">{detail.status}</span>
            {typeof detail.checks_total === 'number' && detail.checks_total > 0
              ? ` · ${detail.checks_passed}/${detail.checks_total} checks passed`
              : ''}
          </p>
          {Array.isArray(detail.packages) && detail.packages.length > 0 && (
            <p className="text-sm text-[var(--hb-muted)]">Generated: {detail.packages.join(' · ')}</p>
          )}
          {detail.no_live_writes && (
            <p className="text-xs text-emerald-300 mt-1">
              No changes were made to the live project data or database.
            </p>
          )}
          {detail.message && <p className="text-sm text-rose-300 mt-1">{detail.message}</p>}
        </div>
      )}
    </div>
  )
}
