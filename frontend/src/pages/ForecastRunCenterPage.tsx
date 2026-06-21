/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — Run Center (Implementation Phase 3 + DB-config-backed generation).
 * Lets an operator generate a deterministic context→analysis forecast, OR generate the comprehensive
 * package CONSUMING the live config snapshot (so a promoted config drives generation). Generation
 * writes only to an isolated work area and never changes the live data or database; the live config
 * DB is read-only. Business labels only — no paths, run stamps, or internals are shown. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { StatusPill } from './ForecastingPage'
import { api } from '../lib/api'
import type { ForecastGeneratorKind } from '../lib/api'

type Selected = { id: string; source: 'file' | 'live_config' }

const GENERATOR_KINDS: { value: ForecastGeneratorKind; label: string }[] = [
  { value: 'comprehensive', label: 'Comprehensive' },
  { value: 'model_controls', label: 'Model controls' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'probability', label: 'Probabilistic' },
]

export function ForecastRunCenterPage() {
  const { data: runsResp, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'runs'],
    queryFn: () => api.getForecastRuns(),
  })
  const { data: dbRunsResp, refetch: refetchDb } = useQuery({
    queryKey: ['forecast', 'runs', 'db-config'],
    queryFn: () => api.getForecastDbConfigRuns(),
  })

  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [genUnconfigured, setGenUnconfigured] = useState(false)

  const [genDb, setGenDb] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)
  const [dbDisabled, setDbDisabled] = useState(false)
  const [genKind, setGenKind] = useState<ForecastGeneratorKind>('comprehensive')

  const [selected, setSelected] = useState<Selected | undefined>(undefined)

  const { data: detailResp } = useQuery({
    queryKey: ['forecast', 'run-detail', selected?.source, selected?.id],
    queryFn: () =>
      selected?.source === 'live_config'
        ? api.getForecastDbConfigRun(selected.id)
        : api.getForecastRun(selected!.id),
    enabled: Boolean(selected),
  })

  async function onGenerate() {
    setGenerating(true)
    setGenError(null)
    setGenUnconfigured(false)
    try {
      await api.startForecastRun()
      await refetch()
    } catch (e: any) {
      setGenUnconfigured(e?.status === 503)
      setGenError(
        e?.status === 503
          ? 'Forecast generation is not configured in this environment yet.'
          : 'The forecast generation could not be started.',
      )
    } finally {
      setGenerating(false)
    }
  }

  async function onGenerateDbConfig() {
    setGenDb(true)
    setDbError(null)
    setDbDisabled(false)
    try {
      await api.startForecastDbConfigRun(genKind)
      await refetchDb()
    } catch (e: any) {
      setDbDisabled(e?.status === 503)
      setDbError(
        e?.status === 503
          ? 'Generating from live config isn’t enabled in this environment.'
          : 'Generating from live config could not be started.',
      )
    } finally {
      setGenDb(false)
    }
  }

  const fileRuns: any[] = Array.isArray(runsResp?.runs) ? runsResp.runs : []
  const dbRuns: any[] = Array.isArray(dbRunsResp?.runs) ? dbRunsResp.runs : []
  const allRuns = [
    ...fileRuns.map((r) => ({ ...r, _source: 'file' as const })),
    ...dbRuns.map((r) => ({ ...r, _source: 'live_config' as const })),
  ].sort((a, b) => String(b.generated_display || '').localeCompare(String(a.generated_display || '')))
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
        {genError && (
          <p className="text-sm text-rose-300 mt-2">
            {genError}
            {genUnconfigured && (
              <>
                {' '}
                <Link to="/forecasting/runtime" className="underline">
                  Configure data sources →
                </Link>
              </>
            )}
          </p>
        )}
      </div>

      <div className="card mt-3">
        <div className="flex items-center justify-between gap-3">
          <div className="section-title">Generate from live config</div>
          <div className="flex items-center gap-2">
            <label htmlFor="db-config-kind" className="text-sm text-[var(--hb-muted)]">
              Forecast
            </label>
            <select
              id="db-config-kind"
              aria-label="Forecast type"
              value={genKind}
              onChange={(e) => setGenKind(e.target.value as ForecastGeneratorKind)}
              disabled={genDb}
              className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
            >
              {GENERATOR_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={onGenerateDbConfig}
              disabled={genDb}
              className="rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {genDb ? 'Generating…' : 'Generate from live config'}
            </button>
          </div>
        </div>
        <p className="text-sm text-[var(--hb-muted)]">
          Generates the comprehensive forecast using the current promoted configuration from the
          system of record. The configuration is verified before the run; the live data and database
          are never changed.
        </p>
        {dbError && (
          <p className="text-sm text-rose-300 mt-2">
            {dbError}
            {dbDisabled && (
              <>
                {' '}
                <Link to="/forecasting/runtime" className="underline">
                  Data sources →
                </Link>
              </>
            )}
          </p>
        )}
      </div>

      <div className="card mt-3">
        <div className="section-title">Run history</div>
        {isLoading ? (
          <div className="text-sm text-[var(--hb-muted)]">Loading runs…</div>
        ) : error ? (
          <EmptyState title="Runs unavailable" hint="We could not load the run history right now." />
        ) : allRuns.length === 0 ? (
          <EmptyState title="No runs yet" hint="Generate a forecast to see it here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Run</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Generated</th>
                  <th className="py-2 pr-3"></th>
                </tr>
              </thead>
              <tbody>
                {allRuns.map((r: any) => (
                  <tr key={`${r._source}:${r.run_id}`} className="border-b border-[var(--hb-border)]">
                    <td className="py-2 pr-3">{r.display_label}</td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">
                      {r._source === 'live_config' ? 'Live config' : 'File config'}
                    </td>
                    <td className="py-2 pr-3">
                      <StatusPill
                        status={
                          r.status === 'succeeded' || r.status === 'generated'
                            ? 'validated'
                            : 'attention'
                        }
                      />
                    </td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">{r.generated_display || '—'}</td>
                    <td className="py-2 pr-3">
                      <button
                        type="button"
                        onClick={() => setSelected({ id: r.run_id, source: r._source })}
                        className="underline"
                      >
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
          {detail.config_snapshot_consumed && (
            <p className="text-sm text-[var(--hb-muted)]">
              Configuration: <span className="font-medium">{detail.snapshot_display || 'live config'}</span>
              {typeof detail.snapshot_item_count === 'number' && detail.snapshot_item_count > 0
                ? ` (${detail.snapshot_item_count} settings)`
                : ''}
              {detail.fidelity_gate_passed ? ' · Configuration verified ✓' : ''}
            </p>
          )}
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
