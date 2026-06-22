/* Forecast generation — isolated packages; never writes live data (Phase 3). */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastActionButton,
  ForecastActionLink,
  ForecastBackLink,
  ForecastPageHeader,
  ForecastQuickLink,
  ForecastShell,
  ForecastSubnav,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPageChrome'
import { ForecastStatusPill } from '../components/forecast/ForecastStatusPill'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'
import type { ForecastGeneratorKind } from '../lib/api'

type Selected = { id: string; source: 'file' | 'live_config' }

const GENERATOR_KINDS: { value: ForecastGeneratorKind; label: string }[] = [
  { value: 'comprehensive', label: 'Comprehensive' },
  { value: 'model_controls', label: 'Model controls' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'probability', label: 'Probabilistic' },
]

function runStatusPill(status: string | undefined): string {
  if (status === 'succeeded' || status === 'generated') return 'validated'
  if (status === 'failed') return 'invalid'
  return 'attention'
}

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
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setGenUnconfigured(status === 503)
      setGenError(
        status === 503
          ? 'Generation is not ready yet. Check storage settings first.'
          : 'Forecast generation could not be started.',
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
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setDbDisabled(status === 503)
      setDbError(
        status === 503
          ? 'Config-backed generation is not enabled in this environment.'
          : 'Config-backed generation could not be started.',
      )
    } finally {
      setGenDb(false)
    }
  }

  const fileRuns = Array.isArray(runsResp?.runs) ? runsResp.runs : []
  const dbRuns = Array.isArray(dbRunsResp?.runs) ? dbRunsResp.runs : []
  const allRuns = [
    ...fileRuns.map((r: Record<string, unknown>) => ({ ...r, _source: 'file' as const })),
    ...dbRuns.map((r: Record<string, unknown>) => ({ ...r, _source: 'live_config' as const })),
  ].sort((a, b) =>
    String(b.generated_display || '').localeCompare(String(a.generated_display || '')),
  )
  const detail = detailResp || null

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Generate forecast"
          subtitle="Creates an isolated forecast package using current local storage and configuration. Procore and live project data are never modified."
          actions={
            <ForecastActionButton onClick={onGenerate} disabled={generating}>
              {generating ? 'Generating…' : 'Generate forecast'}
            </ForecastActionButton>
          }
        />
        {genError && (
          <p className="text-sm text-rose-300 mt-2">
            {genError}
            {genUnconfigured && (
              <>
                {' '}
                <ForecastActionLink to="/forecasting/runtime">Open storage settings</ForecastActionLink>
              </>
            )}
          </p>
        )}
      </section>

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Generate from live configuration"
          subtitle="Uses the promoted configuration snapshot from the local database. Still read-only toward live systems."
          actions={
            <div className="flex items-center gap-2">
              <label htmlFor="db-config-kind" className="text-sm text-[var(--hb-muted)]">
                Type
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
              <ForecastActionButton onClick={onGenerateDbConfig} disabled={genDb}>
                {genDb ? 'Generating…' : 'Generate'}
              </ForecastActionButton>
            </div>
          }
        />
        {dbError && (
          <p className="text-sm text-rose-300 mt-2">
            {dbError}
            {dbDisabled && (
              <>
                {' '}
                <ForecastActionLink to="/forecasting/runtime">Storage settings</ForecastActionLink>
              </>
            )}
          </p>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Generation history</h2>
        {isLoading ? (
          <div className="text-sm text-[var(--hb-muted)]">Loading history…</div>
        ) : error ? (
          <EmptyState title="History unavailable" hint="We could not load generation history right now." />
        ) : allRuns.length === 0 ? (
          <EmptyState
            title="No forecast runs yet"
            hint="Generate your first forecast to see it here. Output stays in local workspaces only."
            actions={
              <ForecastActionButton onClick={onGenerate} disabled={generating}>
                Generate first forecast
              </ForecastActionButton>
            }
          />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Run</ForecastTh>
                <ForecastTh>Source</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Generated</ForecastTh>
                <ForecastTh />
              </>
            }
          >
            {allRuns.map((r) => (
              <tr key={`${r._source}:${r.run_id as string}`}>
                <ForecastTd>{r.display_label as string}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {r._source === 'live_config' ? 'Live configuration' : 'File configuration'}
                </ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={runStatusPill(r.status as string)} />
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {(r.generated_display as string) || '—'}
                </ForecastTd>
                <ForecastTd>
                  <ForecastActionButton
                    variant="ghost"
                    onClick={() => setSelected({ id: r.run_id as string, source: r._source })}
                  >
                    Open
                  </ForecastActionButton>
                </ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>

      {detail && (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">{(detail.display_label as string) || 'Run detail'}</h2>
          <p className="text-sm">
            Status: <span className="font-medium">{detail.status as string}</span>
            {typeof detail.checks_total === 'number' && detail.checks_total > 0
              ? ` · ${detail.checks_passed}/${detail.checks_total} checks passed`
              : ''}
          </p>
          {detail.config_snapshot_consumed && (
            <p className="text-sm text-[var(--hb-muted)]">
              Configuration:{' '}
              <span className="font-medium">
                {(detail.snapshot_display as string) || 'live configuration'}
              </span>
              {typeof detail.snapshot_item_count === 'number' && detail.snapshot_item_count > 0
                ? ` (${detail.snapshot_item_count} settings)`
                : ''}
              {detail.fidelity_gate_passed ? ' · Verified' : ''}
            </p>
          )}
          {Array.isArray(detail.packages) && detail.packages.length > 0 && (
            <p className="text-sm text-[var(--hb-muted)]">
              Packages: {(detail.packages as string[]).join(' · ')}
            </p>
          )}
          {detail.no_live_writes && (
            <p className="text-xs text-emerald-300 mt-1">
              No changes were made to live project data or external systems.
            </p>
          )}
          {detail.message && (
            <p className="text-sm text-rose-300 mt-1">{detail.message as string}</p>
          )}
          <div className="mt-2">
            <ForecastQuickLink to="/forecasting">Review packages on overview</ForecastQuickLink>
          </div>
        </section>
      )}
    </ForecastShell>
  )
}