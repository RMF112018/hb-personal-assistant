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
import { ForecastDecisionSupportPanel } from '../components/forecast/ForecastDecisionSupportPanel'
import { ForecastNarrativesPanel } from '../components/forecast/ForecastNarrativesPanel'
import { ForecastOperatorAssumptionsPanel } from '../components/forecast/ForecastOperatorAssumptionsPanel'
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

// Coded readiness reasons → actionable, path-free copy. Mirrors the backend reason codes from
// GET /api/forecast/generation/readiness so an operator sees WHY generation is blocked before click.
const READINESS_REASON_TEXT: Record<string, string> = {
  db_config_run_disabled: "Generating from live configuration isn't enabled in this environment.",
  forecast_runtime_storage_not_configured: 'Forecast storage is not configured yet.',
  config_db_not_ready: 'The configuration database is not available yet.',
  cfr_src_not_available: 'The forecast engine source is not available.',
}

// Non-blocking readiness advisories (generation is allowed, but may not produce useful output).
const READINESS_WARNING_TEXT: Record<string, string> = {
  config_db_has_no_snapshots:
    'No configuration snapshot has been promoted yet, so generation may have nothing to run.',
}

// Action codes from the backend mapped to UI routes (the backend stays path/route-free). Codes
// without a route render as plain label text.
const READINESS_ACTION_ROUTE: Record<string, string> = {
  enable_db_config_run: '/forecasting/runtime',
  open_storage_settings: '/forecasting/runtime',
}

// Per-project readiness reason codes → actionable, table-name-free copy (P-B). Mirrors the backend
// reason codes from GET /api/forecast/generation/projects.
const PROJECT_READINESS_REASON_TEXT: Record<string, string> = {
  missing_config_snapshot: 'No configuration snapshot is available for this project.',
  missing_budget_cost_data: 'Budget and cost data is not available for this project yet.',
  missing_schedule_data: 'No schedule data has been imported for this project yet.',
  generation_disabled: "Generating from live configuration isn't enabled in this environment.",
  no_project_identity: 'This project cannot be resolved to a known source.',
  no_prior_forecast_output: 'No prior forecast has been generated for this project yet.',
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
  // Readiness for DB-config-backed generation: lets us disable the control BEFORE click and explain
  // why, instead of catching a raw 503 afterwards. The backend POST stays fail-closed regardless.
  const { data: readiness } = useQuery({
    queryKey: ['forecast', 'generation', 'readiness'],
    queryFn: () => api.getForecastGenerationReadiness(),
    staleTime: 15_000,
  })

  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [genUnconfigured, setGenUnconfigured] = useState(false)

  const [genDb, setGenDb] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)
  const [dbDisabled, setDbDisabled] = useState(false)
  const [genKind, setGenKind] = useState<ForecastGeneratorKind>('comprehensive')

  const [selected, setSelected] = useState<Selected | undefined>(undefined)

  // P-B: project selector driven by the generation-ready read model (procore identity + committed
  // schedule + forecast outputs), with per-project readiness. No 'tropical' fallback for generation.
  const { data: projectsResp } = useQuery({
    queryKey: ['forecast', 'generation', 'projects'],
    queryFn: () => api.getForecastGenerationProjects(),
  })
  const projects = projectsResp?.projects ?? []
  const [projectKey, setProjectKey] = useState<string | undefined>(undefined)
  const selectedProjectObj = projects.find((p) => p.project_key === projectKey)
  const selectedBlocked = selectedProjectObj?.readiness_status === 'blocked'
  // Browse panels may default to the first available project (never a hardcoded 'tropical').
  const browseProject = projectKey ?? projects[0]?.project_key

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
      await api.startForecastDbConfigRun(genKind, projectKey)
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

  // Disable the DB-config control only when readiness is KNOWN not-ready (fail-open during the brief
  // load; the backend POST is still fail-closed). Reasons drive the actionable before-click message.
  const dbNotReady = readiness?.ready === false
  const disabledReasons = readiness?.disabled_reasons ?? []
  const readinessActions = readiness?.actions ?? []
  const readinessWarnings = readiness?.warnings ?? []

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Project"
          subtitle="Select a project to generate a forecast. Availability reflects the latest local database evidence."
          actions={
            <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
              Project
              <select
                aria-label="Forecast project"
                className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm disabled:opacity-50"
                value={projectKey ?? ''}
                onChange={(e) => setProjectKey(e.target.value || undefined)}
                disabled={projects.length === 0}
              >
                <option value="" disabled>
                  Select a project
                </option>
                {projects.map((p) => (
                  <option key={p.project_key} value={p.project_key}>
                    {(p.display_name || p.project_key) +
                      (p.readiness_status !== 'ready' ? ` — ${p.readiness_status}` : '')}
                  </option>
                ))}
              </select>
            </label>
          }
        />
        {projects.length === 0 && (
          <p className="text-sm text-[var(--hb-muted)] mt-2">No projects are available yet.</p>
        )}
        {selectedProjectObj && selectedProjectObj.readiness_status !== 'ready' && (
          <div className="text-sm text-rose-300 mt-2" role="status">
            {selectedProjectObj.readiness_reasons.map((reason) => (
              <p key={reason}>
                {PROJECT_READINESS_REASON_TEXT[reason] ??
                  'This project is not ready for generation.'}
              </p>
            ))}
          </div>
        )}
      </section>

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
                disabled={genDb || dbNotReady}
                className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
              >
                {GENERATOR_KINDS.map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </select>
              <ForecastActionButton
                onClick={onGenerateDbConfig}
                disabled={genDb || dbNotReady || !projectKey || selectedBlocked}
              >
                {genDb ? 'Generating…' : 'Generate'}
              </ForecastActionButton>
            </div>
          }
        />
        {dbNotReady && (
          <div className="text-sm text-rose-300 mt-2" role="status">
            {disabledReasons.map((reason) => (
              <p key={reason}>
                {READINESS_REASON_TEXT[reason] ?? 'Generation from live configuration is not available yet.'}
              </p>
            ))}
            {readinessActions.map((action) => {
              const route = READINESS_ACTION_ROUTE[action.code]
              return (
                <p key={action.code}>
                  {route ? (
                    <ForecastActionLink to={route}>{action.label}</ForecastActionLink>
                  ) : (
                    action.label
                  )}
                </p>
              )
            })}
          </div>
        )}
        {!dbNotReady && readinessWarnings.length > 0 && (
          <div className="text-sm text-amber-300 mt-2" role="status">
            {readinessWarnings.map((w) => (
              <p key={w}>
                {READINESS_WARNING_TEXT[w] ??
                  'Generation may not produce output in the current configuration.'}
              </p>
            ))}
          </div>
        )}
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

      {browseProject && (
        <>
          <ForecastDecisionSupportPanel project={browseProject} />
          <ForecastNarrativesPanel project={browseProject} />
          <ForecastOperatorAssumptionsPanel project={browseProject} />
        </>
      )}
    </ForecastShell>
  )
}